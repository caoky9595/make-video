import asyncio
import edge_tts

async def main():
    comm = edge_tts.Communicate("Thử nghiệm.", "vi-VN-HoaiMyNeural")
    async for chunk in comm.stream():
        if chunk["type"] == "SentenceBoundary":
            print("SENTENCE BND:", chunk)

asyncio.run(main())
