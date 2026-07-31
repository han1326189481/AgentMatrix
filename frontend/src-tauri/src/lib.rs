use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command as StdCommand};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use tauri::Manager;
use tauri::Emitter;
use tauri::tray::TrayIconBuilder;

// ── 指数退避参数 ──
const BACKOFF_SEQUENCE: [u64; 6] = [1, 2, 4, 8, 10, 10];
const MAX_FAILURES: usize = 6;
const HEALTH_CHECK_URL: &str = "http://127.0.0.1:8000/health";
const HEALTH_CHECK_TIMEOUT_SECS: u64 = 90;
const HEALTH_CHECK_INTERVAL_MS: u64 = 500;
const GRACEFUL_SHUTDOWN_TIMEOUT_SECS: u64 = 5;

// ── Sidecar 状态 ──
struct SidecarState {
    child: Option<Child>,
    pid: Option<u32>,
    backoff_attempt: usize,
    permanent_failure: bool,
    backend_ready: bool,
}

// ── Sidecar 管理器 ──
pub struct SidecarManager {
    state: Mutex<SidecarState>,
    backend_dir: PathBuf,
    shutting_down: AtomicBool,
}

impl SidecarManager {
    pub fn new(backend_dir: PathBuf) -> Self {
        Self {
            state: Mutex::new(SidecarState {
                child: None,
                pid: None,
                backoff_attempt: 0,
                permanent_failure: false,
                backend_ready: false,
            }),
            backend_dir,
            shutting_down: AtomicBool::new(false),
        }
    }

    /// 获取后端目录路径
    pub fn backend_dir() -> PathBuf {
        // 开发环境: 使用相对路径 ../backend
        // 打包环境: 使用 Tauri resource_dir
        let exe_path = std::env::current_exe().unwrap_or_default();
        let exe_dir = exe_path.parent().unwrap_or(&std::path::Path::new("."));

        // 打包环境 1: 查找 resources/backend/ 目录（Tauri resources 配置标准路径）
        let resources_backend = exe_dir.join("resources").join("backend");
        if resources_backend.exists() {
            return resources_backend;
        }

        // 打包环境 2: 查找 backend/ 目录（NSIS 安装后的实际路径）
        let direct_backend = exe_dir.join("backend");
        if direct_backend.exists() {
            return direct_backend;
        }

        // 开发环境: src-tauri/ 的父目录 + backend
        let dev_backend = std::env::current_dir()
            .unwrap_or_default()
            .parent()
            .map(|p| p.join("backend"))
            .unwrap_or_else(|| PathBuf::from("../backend"));

        std::path::absolute(&dev_backend).unwrap_or(dev_backend)
    }

    // ── 6.3: 启动后端（含指数退避重试） ──
    pub fn start_with_backoff(&self) -> Result<(), String> {
        let mut state = self.state.lock().map_err(|e| e.to_string())?;
        state.permanent_failure = false;
        state.backoff_attempt = 0;
        state.backend_ready = false;
        drop(state);

        loop {
            let attempt = {
                let st = self.state.lock().map_err(|e| e.to_string())?;
                st.backoff_attempt
            };

            if attempt >= MAX_FAILURES {
                let mut st = self.state.lock().map_err(|e| e.to_string())?;
                st.permanent_failure = true;
                println!(
                    "[AgentMatrix] Backend startup failed after {} attempts — permanent failure",
                    MAX_FAILURES
                );
                return Err(format!(
                    "Backend failed to start after {} attempts",
                    MAX_FAILURES
                ));
            }

            let delay = BACKOFF_SEQUENCE[attempt];
            println!(
                "[AgentMatrix] Backend startup attempt {}/{} — waiting {}s before retry",
                attempt + 1,
                MAX_FAILURES,
                delay
            );

            if attempt > 0 {
                thread::sleep(Duration::from_secs(delay));
            }

            // 尝试启动
            match self.spawn_backend() {
                Ok(()) => {
                    // 等待端口就绪
                    match self.wait_for_ready(HEALTH_CHECK_TIMEOUT_SECS) {
                        Ok(()) => {
                            let mut st = self.state.lock().map_err(|e| e.to_string())?;
                            st.backend_ready = true;
                            st.backoff_attempt = 0;
                            println!("[AgentMatrix] Backend is ready");
                            return Ok(());
                        }
                        Err(e) => {
                            println!(
                                "[AgentMatrix] Backend started but health check failed: {}",
                                e
                            );
                            self.kill_current_process();
                            let mut st = self.state.lock().map_err(|e| e.to_string())?;
                            st.backoff_attempt += 1;
                        }
                    }
                }
                Err(e) => {
                    println!("[AgentMatrix] Failed to spawn backend: {}", e);
                    let mut st = self.state.lock().map_err(|e| e.to_string())?;
                    st.backoff_attempt += 1;
                }
            }
        }
    }

    /// 释放端口 8000（杀掉占用端口的旧进程）
    fn free_port_8000() {
        #[cfg(target_os = "windows")]
        {
            // 查找占用端口 8000 的进程 PID
            let output = StdCommand::new("cmd")
                .args(["/C", "netstat -ano | findstr :8000 | findstr LISTENING"])
                .output();
            if let Ok(output) = output {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines() {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if let Some(pid_str) = parts.last() {
                        if let Ok(pid) = pid_str.parse::<u32>() {
                            println!(
                                "[AgentMatrix] Found orphaned process on port 8000 (PID {}), killing...",
                                pid
                            );
                            let _ = StdCommand::new("taskkill")
                                .args(["/F", "/PID", &pid.to_string()])
                                .stdout(std::process::Stdio::null())
                                .stderr(std::process::Stdio::null())
                                .status();
                        }
                    }
                }
            }
        }
    }

    /// 启动 Python 进程（或 PyInstaller 打包的 EXE）
    fn spawn_backend(&self) -> Result<(), String> {
        let mut state = self.state.lock().map_err(|e| e.to_string())?;

        // 先清理旧进程
        if let Some(ref mut child) = state.child {
            let _ = child.kill();
            let _ = child.wait();
        }

        // 释放端口 8000（杀掉可能的孤儿进程）
        Self::free_port_8000();

        let backend_dir = self.backend_dir.clone();

        // 7.8: 检测 PyInstaller 打包的 EXE
        let exe_path = backend_dir.join("agentmatrix-backend.exe");
        let (program, args, cwd) = if exe_path.exists() {
            println!(
                "[AgentMatrix] Found packaged EXE: {:?}",
                exe_path
            );
            (exe_path.to_string_lossy().to_string(), vec![], backend_dir.clone())
        } else {
            // 开发模式：使用 uvicorn 模块启动（不依赖 start_uvicorn.py 脚本）
            println!(
                "[AgentMatrix] Starting Python backend from: {:?}",
                backend_dir
            );
            (
                "python".to_string(),
                vec![
                    "-m".to_string(),
                    "uvicorn".to_string(),
                    "app.main:socket_app".to_string(),
                    "--host".to_string(),
                    "127.0.0.1".to_string(),
                    "--port".to_string(),
                    "8000".to_string(),
                ],
                backend_dir.clone(),
            )
        };

        let mut cmd = StdCommand::new(&program);
        for arg in &args {
            cmd.arg(arg);
        }
        cmd.current_dir(&cwd)
            .stdout(std::process::Stdio::piped())
            .stderr(std::process::Stdio::piped());

        #[cfg(target_os = "windows")]
        {
            use std::os::windows::process::CommandExt;
            const CREATE_NO_WINDOW: u32 = 0x08000000;
            cmd.creation_flags(CREATE_NO_WINDOW);
        }

        let child = cmd.spawn().map_err(|e| format!("Failed to spawn Python: {}", e))?;
        let pid = child.id();
        println!("[AgentMatrix] Backend started with PID: {}", pid);

        // 消费 stdout/stderr
        let mut child_mut = child;
        if let Some(stdout) = child_mut.stdout.take() {
            let reader = BufReader::new(stdout);
            thread::spawn(move || {
                for line in reader.lines() {
                    if let Ok(line) = line {
                        println!("[Backend:{}] {}", pid, line);
                    }
                }
            });
        }
        if let Some(stderr) = child_mut.stderr.take() {
            let reader = BufReader::new(stderr);
            thread::spawn(move || {
                for line in reader.lines() {
                    if let Ok(line) = line {
                        eprintln!("[Backend:{}] {}", pid, line);
                    }
                }
            });
        }

        state.child = Some(child_mut);
        state.pid = Some(pid);

        Ok(())
    }

    // ── 6.6: 端口就绪等待 ──
    pub fn wait_for_ready(&self, timeout_secs: u64) -> Result<(), String> {
        let start = Instant::now();
        let timeout = Duration::from_secs(timeout_secs);
        let interval = Duration::from_millis(HEALTH_CHECK_INTERVAL_MS);

        println!(
            "[AgentMatrix] Waiting for backend to be ready (timeout: {}s)...",
            timeout_secs
        );

        loop {
            if start.elapsed() >= timeout {
                return Err(format!(
                    "Health check timed out after {}s",
                    timeout_secs
                ));
            }

            if self.shutting_down.load(Ordering::Relaxed) {
                return Err("Shutting down, aborting health check".to_string());
            }

            match ureq::get(HEALTH_CHECK_URL).call() {
                Ok(response) => {
                    if response.status() == 200 {
                        let elapsed = start.elapsed().as_secs_f64();
                        println!(
                            "[AgentMatrix] Backend ready after {:.1}s",
                            elapsed
                        );
                        return Ok(());
                    }
                    println!(
                        "[AgentMatrix] Health check returned {}, retrying...",
                        response.status()
                    );
                }
                Err(_) => {
                    // 后端尚未就绪，继续等待
                }
            }

            thread::sleep(interval);
        }
    }

    // ── 6.7: 优雅关闭 ──
    pub fn graceful_shutdown(&self) {
        self.shutting_down.store(true, Ordering::Relaxed);
        println!("[AgentMatrix] Shutting down backend gracefully...");

        let pid = {
            let state = self.state.lock().unwrap();
            state.pid
        };

        if let Some(pid) = pid {
            println!("[AgentMatrix] Sending terminate signal to PID {}", pid);

            #[cfg(target_os = "windows")]
            {
                // 使用 taskkill 优雅关闭进程树
                let _ = StdCommand::new("taskkill")
                    .args(["/PID", &pid.to_string()])
                    .stdout(std::process::Stdio::null())
                    .stderr(std::process::Stdio::null())
                    .spawn();
            }

            #[cfg(not(target_os = "windows"))]
            {
                // Unix: SIGTERM
                let _ = StdCommand::new("kill")
                    .arg(pid.to_string())
                    .stdout(std::process::Stdio::null())
                    .stderr(std::process::Stdio::null())
                    .spawn();
            }

            // 等待优雅关闭
            let grace_start = Instant::now();
            let grace_timeout = Duration::from_secs(GRACEFUL_SHUTDOWN_TIMEOUT_SECS);

            loop {
                if grace_start.elapsed() >= grace_timeout {
                    println!(
                        "[AgentMatrix] Graceful shutdown timeout — force killing PID {}",
                        pid
                    );
                    self.force_kill(pid);
                    break;
                }

                // 检查进程是否还在运行
                if !Self::is_process_running(pid) {
                    println!(
                        "[AgentMatrix] Backend exited gracefully after {:.1}s",
                        grace_start.elapsed().as_secs_f64()
                    );
                    break;
                }

                thread::sleep(Duration::from_millis(200));
            }
        }

        // 清理子进程对象
        if let Ok(mut state) = self.state.lock() {
            if let Some(ref mut child) = state.child {
                let _ = child.wait();
            }
            state.child = None;
            state.pid = None;
            state.backend_ready = false;
            state.backoff_attempt = 0;
            state.permanent_failure = false;
        }

        println!("[AgentMatrix] Backend shutdown complete");
    }

    fn force_kill(&self, pid: u32) {
        #[cfg(target_os = "windows")]
        {
            let _ = StdCommand::new("taskkill")
                .args(["/F", "/PID", &pid.to_string()])
                .stdout(std::process::Stdio::null())
                .stderr(std::process::Stdio::null())
                .spawn();
        }

        #[cfg(not(target_os = "windows"))]
        {
            let _ = StdCommand::new("kill")
                .args(["-9", &pid.to_string()])
                .stdout(std::process::Stdio::null())
                .stderr(std::process::Stdio::null())
                .spawn();
        }
    }

    fn kill_current_process(&self) {
        if let Ok(mut state) = self.state.lock() {
            if let Some(ref mut child) = state.child {
                let pid = child.id();
                println!("[AgentMatrix] Killing current backend process PID {}", pid);
                let _ = child.kill();
                let _ = child.wait();
            }
            state.child = None;
            state.pid = None;
            state.backend_ready = false;
        }
    }

    fn is_process_running(pid: u32) -> bool {
        #[cfg(target_os = "windows")]
        {
            StdCommand::new("tasklist")
                .args(["/FI", &format!("PID eq {}", pid)])
                .stdout(std::process::Stdio::null())
                .stderr(std::process::Stdio::null())
                .status()
                .map(|s| s.success())
                .unwrap_or(false)
        }

        #[cfg(not(target_os = "windows"))]
        {
            StdCommand::new("kill")
                .args(["-0", &pid.to_string()])
                .stdout(std::process::Stdio::null())
                .stderr(std::process::Stdio::null())
                .status()
                .map(|s| s.success())
                .unwrap_or(false)
        }
    }

    // ── 6.4: 重启 ──
    pub fn restart_backend(&self) -> Result<(), String> {
        println!("[AgentMatrix] Restarting backend...");

        // 重置状态
        {
            let mut st = self.state.lock().map_err(|e| e.to_string())?;
            st.permanent_failure = false;
            st.backoff_attempt = 0;
            st.backend_ready = false;
        }

        self.shutting_down.store(false, Ordering::Relaxed);

        // 先杀掉当前进程
        self.kill_current_process();

        // 等待端口释放
        thread::sleep(Duration::from_millis(500));

        // 重新启动
        self.start_with_backoff()
    }

    // ── 状态查询 ──
    pub fn is_ready(&self) -> bool {
        self.state
            .lock()
            .map(|s| s.backend_ready)
            .unwrap_or(false)
    }

    pub fn is_permanent_failure(&self) -> bool {
        self.state
            .lock()
            .map(|s| s.permanent_failure)
            .unwrap_or(false)
    }

    pub fn get_backoff_status(&self) -> BackoffStatus {
        let st = self.state.lock().unwrap();
        BackoffStatus {
            attempt: st.backoff_attempt,
            max_attempts: MAX_FAILURES,
            permanent_failure: st.permanent_failure,
            backend_ready: st.backend_ready,
            backoff_sequence: BACKOFF_SEQUENCE.to_vec(),
            current_delay_ms: if st.backoff_attempt > 0 && st.backoff_attempt <= MAX_FAILURES
            {
                Some(BACKOFF_SEQUENCE[st.backoff_attempt - 1] * 1000)
            } else {
                None
            },
        }
    }
}

// ── 状态序列化结构 ──
#[derive(serde::Serialize, Clone)]
pub struct BackoffStatus {
    pub attempt: usize,
    pub max_attempts: usize,
    pub permanent_failure: bool,
    pub backend_ready: bool,
    pub backoff_sequence: Vec<u64>,
    pub current_delay_ms: Option<u64>,
}

// ── Tauri 命令 ──

#[tauri::command]
fn restart_sidecar(
    manager: tauri::State<'_, Arc<SidecarManager>>,
) -> Result<String, String> {
    manager.restart_backend()?;
    Ok("Backend restarted successfully".to_string())
}

#[tauri::command]
fn get_sidecar_status(
    manager: tauri::State<'_, Arc<SidecarManager>>,
) -> Result<BackoffStatus, String> {
    Ok(manager.get_backoff_status())
}

// ── 应用入口 ──

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let backend_dir = SidecarManager::backend_dir();
    let manager = Arc::new(SidecarManager::new(backend_dir));

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(manager.clone())
        .invoke_handler(tauri::generate_handler![restart_sidecar, get_sidecar_status])
        .setup(move |app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            // 6.9: 配置系统托盘图标
            let _tray = TrayIconBuilder::new()
                .tooltip("AgentMatrix — 多智能体动态协同平台")
                .on_tray_icon_event(|tray, event| {
                    if let tauri::tray::TrayIconEvent::Click { .. } = event {
                        let _ = tray.app_handle().get_webview_window("main").map(|w| {
                            w.show().ok();
                            w.set_focus().ok();
                        });
                    }
                })
                .build(app)?;

            // 启动后端（带指数退避）
            let mgr = manager.clone();
            let app_handle = app.handle().clone();
            thread::spawn(move || {
                match mgr.start_with_backoff() {
                    Ok(()) => {
                        // 通知前端后端已就绪
                        let _ = app_handle.emit("backend-ready", true);
                    }
                    Err(e) => {
                        eprintln!("[AgentMatrix] Backend startup failed: {}", e);
                        let _ = app_handle.emit("backend-error", e);
                    }
                }
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // 获取 SidecarManager 并执行优雅关闭
                if let Some(manager) = window.app_handle().try_state::<Arc<SidecarManager>>() {
                    manager.graceful_shutdown();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}