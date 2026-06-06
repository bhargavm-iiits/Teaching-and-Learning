import asyncio
import json
import websockets

async def test_ws():
    uri = "ws://localhost:8000/ws/lesson"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")
            
            # 1. Start lesson
            start_payload = {
                "event": "start_lesson",
                "student_id": "test_student_123",
                "topic_code": "MOTION_SPEED",
                "subject_code": "PHY"
            }
            print(f"\nSending start_lesson: {json.dumps(start_payload)}")
            await websocket.send(json.dumps(start_payload))
            
            # 2. Read incoming manifest
            print("\nWaiting for authored manifest...")
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                print(f"Received: Event='{data.get('event')}'")
                if data.get('event') == 'manifest':
                    session_id = data.get('session_id')
                    print(f"Manifest received! Session ID: {session_id}")
                    print(f"Curriculum Title: {data.get('manifest', {}).get('lesson_title')}")
                    break
            
            # 3. Simulate quiz failure (triggers adaptation)
            telemetry_payload = {
                "event": "telemetry",
                "session_id": session_id,
                "events": [
                    {
                        "type": "quiz_attempt",
                        "value": "wrong",
                        "data": {
                            "correct": False,
                            "duration_ms": 5000
                        }
                    }
                ]
            }
            print(f"\nSending Quiz Failure Telemetry (should trigger adaptation): {json.dumps(telemetry_payload)}")
            await websocket.send(json.dumps(telemetry_payload))
            
            # 4. Wait for adaptation patch
            print("\nWaiting for real-time manifest_patch response...")
            response = await websocket.recv()
            data = json.loads(response)
            print(f"Received: Event='{data.get('event')}'")
            if data.get('event') == 'manifest_patch':
                print(f"Success! Received live adaptation patch from Agent E:")
                print(json.dumps(data.get('manifest_patch'), indent=2))
                
            # 5. Complete lesson
            complete_payload = {
                "event": "complete_lesson",
                "session_id": session_id
            }
            print(f"\nSending complete_lesson: {json.dumps(complete_payload)}")
            await websocket.send(json.dumps(complete_payload))
            
            # Wait for final close message
            response = await websocket.recv()
            print(f"Received final message: {response}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ws())
