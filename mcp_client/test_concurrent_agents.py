"""
Test script to verify the concurrent agent creation pattern works correctly
"""

import asyncio
import time
from services import InsuranceService

async def test_concurrent_agent_creation():
    """Test that multiple agents can be created concurrently without issues"""
    
    # Create multiple service instances (simulating multiple requests)
    services = [InsuranceService() for _ in range(5)]
    
    async def create_and_test_agent(service_instance, request_id):
        """Create an agent and test basic functionality"""
        start_time = time.time()
        
        try:
            # This should create a new agent instance using shared model
            agent = await service_instance.create_agent()
            creation_time = time.time() - start_time
            
            print(f"Request {request_id}: Agent created in {creation_time:.3f}s")
            print(f"Request {request_id}: Agent ID: {id(agent)}")
            
            # Verify the agent has tools registered
            if hasattr(agent, '_functions') and agent._functions:
                print(f"Request {request_id}: Tools registered: {len(agent._functions)}")
            else:
                print(f"Request {request_id}: No tools found")
                
            return True
            
        except Exception as e:
            print(f"Request {request_id}: Failed - {e}")
            return False
    
    # Run multiple agent creations concurrently
    print("Testing concurrent agent creation...")
    start_time = time.time()
    
    tasks = [
        create_and_test_agent(service, i) 
        for i, service in enumerate(services, 1)
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_time = time.time() - start_time
    
    print(f"\nTotal test time: {total_time:.3f}s")
    print(f"Successful creations: {sum(1 for r in results if r is True)}/{len(results)}")
    
    # Test that shared model is reused
    print("\nTesting shared model reuse...")
    provider1, model1 = await InsuranceService.get_shared_model()
    provider2, model2 = await InsuranceService.get_shared_model()
    
    print(f"Same provider instance: {id(provider1) == id(provider2)}")
    print(f"Same model instance: {id(model1) == id(model2)}")

if __name__ == "__main__":
    asyncio.run(test_concurrent_agent_creation())