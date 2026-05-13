import asyncio
from agents.base.agent_registry import AgentRegistry
from agents.base.agent import AgentInput


async def test_workflow():
    print('Initializing agent registry...')
    registry = AgentRegistry()
    await registry.initialize_all_agents()
    
    print('\nAgent statuses:')
    statuses = registry.get_all_agent_statuses()
    for agent_id, status in statuses.items():
        print(f'  {agent_id}: {status["status"]}')
    
    print('\nTesting simple workflow...')
    user_input = '生成一个校园AI助手方案'
    
    try:
        # Knowledge Agent
        print('1. Knowledge Agent...')
        knowledge_output = await registry.execute_agent('knowledge', AgentInput(content=user_input))
        print(f'   Success: {knowledge_output.success}')
        
        # Summary Agent
        print('2. Summary Agent...')
        summary_output = await registry.execute_agent('summary', AgentInput(content=knowledge_output.content))
        print(f'   Success: {summary_output.success}')
        
        # Writer Agent
        print('3. Writer Agent...')
        writer_output = await registry.execute_agent('writer', AgentInput(content=summary_output.content))
        print(f'   Success: {writer_output.success}')
        
        # Review Agent
        print('4. Review Agent...')
        review_output = await registry.execute_agent('review', AgentInput(content=writer_output.content))
        print(f'   Success: {review_output.success}')
        
        # Judge Agent
        print('5. Judge Agent...')
        judge_output = await registry.execute_agent('judge', AgentInput(content=review_output.content))
        print(f'   Success: {judge_output.success}')
        print(f'   Decision: {judge_output.message}')
        
        # Result Agent
        print('6. Result Agent...')
        result_output = await registry.execute_agent('result', AgentInput(content=judge_output.content, context={'writer': writer_output.content}))
        print(f'   Success: {result_output.success}')
        
        print('\n=== Final Result ===')
        print(result_output.content[:500] + '...' if len(result_output.content) > 500 else result_output.content)
        
        return True
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    asyncio.run(test_workflow())