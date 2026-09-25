from bedrock_agentcore.memory import MemoryClient
client = MemoryClient(region_name="us-east-1")
memory = client.create_memory_and_wait(
    name="WanderBot",
    strategies=[],          # empty = short-term only
    event_expiry_days=7,
)
print(memory.get("id"))     # set this as MEMORY_ID