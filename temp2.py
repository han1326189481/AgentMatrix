    registry
) -> AsyncGenerator[Dict[str, Any], None]:
    """流式执行工作流，实时返回每个步骤的结�?""
    steps: List[WorkflowStep] = []
    current_context = input_data.context or {}
    executed_locally = True
    complexity_score = 0.0
    start_time = time.time()
    
    try:
        agent_order = ["knowledge", "summary", "writer", "review", "judge", "result"]
        agent_names = {
            "knowledge": "Knowledge Agent",
            "summary": "Summary Agent",
            "writer": "Writer Agent",
            "review": "Review Agent",
            "judge": "Judge Agent",
            "result": "Result Agent"
        }
        
        current_input = input_data.user_input
        
        logger.info(f"[STREAM] Starting workflow for input: {input_data.user_input[:50]}...")
        
        yield {
            "type": "start",
            "message": "工作流开始执�?,
            "timestamp": time.time()
        }
        
        for agent_id in agent_order:
            agent_start = time.time()
            agent_name = agent_names.get(agent_id, agent_id)
            
            yield {
                "type": "agent_start",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "timestamp": time.time()
            }
            
            try:
                if agent_id == "summary":
                    agent_input = f"{current_context.get('knowledge', '')}\n\n任务摘要: {current_input}"
                elif agent_id == "writer":
                    agent_input = f"{current_context.get('knowledge', '')}\n\n任务摘要: {current_context.get('summary', '')}"
                elif agent_id == "review":
                    agent_input = f"待评审内�? {current_input}\n任务摘要: {current_context.get('summary', '')}"
                elif agent_id == "judge":
                    agent_input = f"内容: {current_input}\n评审结果: {current_context.get('review', '')}"
                elif agent_id == "result":
                    agent_input = json.dumps({
                        "user_task": input_data.user_input,
                        "summary_result": current_context.get("summary", ""),
                        "review_result": current_context.get("review", ""),
                        "judge_result": current_context.get("judge", ""),
                        "writer_output": current_context.get("writer", ""),
                        "executed_locally": executed_locally,
                        "complexity_score": complexity_score,
                        "judge_decision": "local_output" if executed_locally else "cloud_enhance",
                        "cloud_mode": "none"
                    }, ensure_ascii=False)
                    logger.info(f"[DEBUG] Result Agent input: user_task={input_data.user_input[:50]}..., writer_output exists: {bool(current_context.get('writer'))}")
                else:
                    agent_input = current_input
                
                logger.info(f"[DEBUG] Executing {agent_id} with input length: {len(agent_input)}")
                
                try:
                    output = await asyncio.wait_for(
                        registry.execute_agent(
                            agent_id,
                            AgentInput(content=agent_input, context=current_context, use_llm=True, use_cloud=False)
                        ),
                        timeout=60  # 60秒超�?                    )
                except asyncio.TimeoutError:
                    logger.error(f"[DEBUG] Agent {agent_id} execution timed out")
                    output = AgentOutput(
                        success=False,
                        content=f"Error: Agent {agent_id} 执行超时",
                        metadata={}
                    )
                agent_duration = time.time() - agent_start
                
                step = WorkflowStep(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    input=agent_input[:100] + "..." if len(agent_input) > 100 else agent_input,
                    output=output.content,
                    success=output.success,
                    duration_seconds=agent_duration,
                    metadata=output.metadata or {}
                )
                steps.append(step)
                
                current_context[agent_id] = output.content
                current_input = output.content
                
                yield {
                    "type": "agent_complete",
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "duration": round(agent_duration, 2),
                    "success": output.success,
                    "output_length": len(output.content),
                    "timestamp": time.time()
                }
                
                if agent_id == "judge":
                    executed_locally = step.metadata.get("executed_locally", True)
                    complexity_score = step.metadata.get("complexity_score", 0.0)
            
            except Exception as e:
                agent_duration = time.time() - agent_start
                yield {
                    "type": "agent_error",
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "duration": round(agent_duration, 2),
                    "error": str(e),
                    "timestamp": time.time()
                }
                raise
        
        final_result = steps[-1].output if steps else ""
        total_duration = time.time() - start_time
        
        logger.info(f"[DEBUG] Final result length: {len(final_result)}, first 100 chars: {final_result[:100]}")
        
        yield {
            "type": "complete",
            "final_result": final_result,
            "executed_locally": executed_locally,
            "complexity_score": complexity_score,
            "total_duration": round(total_duration, 2),
            "steps_count": len(steps),
            "timestamp": time.time()
        }
        
    except Exception as e:
        yield {
            "type": "error",
            "error": str(e),
            "timestamp": time.time()
        }
