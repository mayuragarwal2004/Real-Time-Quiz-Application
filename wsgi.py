from app import app, socketio

if __name__ == "__main__":
    print("Starting Real-Time Quiz Application...")
    socketio.run(app, host='0.0.0.0', port=7860)
