"""列出两批测试期间新增并通过质检的知识点"""
import yaml

with open('core/graphs/skill_graph.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

nodes = data.get('nodes', {})
new_nodes = []
for nid, n in nodes.items():
    meta = n.get('metadata', {})
    audit_time = meta.get('audit_time', '')
    # 两批测试时间范围: 13:54 - 14:07
    if audit_time.startswith('2026-07-30T13:5') or audit_time.startswith('2026-07-30T14:0'):
        desc = n.get('description', '')
        preview = desc[:80] + '...' if len(desc) > 80 else desc
        # 去掉换行符方便显示
        preview = preview.replace('\n', ' ')
        new_nodes.append({
            'id': nid,
            'name': n.get('name', ''),
            'domain': n.get('domain', ''),
            'audit_time': audit_time,
            'desc_preview': preview,
        })

new_nodes.sort(key=lambda x: x['audit_time'])

print(f'两批测试期间新增并通过质检的知识点: {len(new_nodes)} 个')
print('=' * 80)
for i, n in enumerate(new_nodes, 1):
    print(f'{i:2d}. [{n["audit_time"]}] {n["name"]}')
    print(f'    域: {n["domain"]}')
    print(f'    描述: {n["desc_preview"]}')
    print()
