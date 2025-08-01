
# No eventlet
# import eventlet
# Force eventlet to be used as the async mode for Flask-SocketIO
# eventlet.monkey_patch()
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import backend  # Import backend functions
import matplotlib.pyplot as plt
import base64
from io import BytesIO
import random
import logging

# Configure the logging level
# logging.getLogger('eventlet.wsgi.server').setLevel(logging.ERROR)
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, async_mode='threading')

exams = backend.load_question_sets()  # Load available exams
selected_questions = []  # Global variable to store the selected questions
current_question = {"index": 0, "answers": {}, "started": False}
participants = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/client')
def client():
    return render_template('client.html')

@app.route('/host')
def host():
    return render_template('host.html', exams=exams)

@socketio.on('join')
def on_join(data):
    username = data['username']
    user_id_number = random.randint(1000, 9999)
    participants[request.sid] = {"user_id_number": user_id_number, "username": username, "score": 0}
    join_room('quiz')
    emit('update_participants', {"participants": participants, "count": len(participants)}, room='quiz')
    print(f"{username} (ID: {user_id_number}) joined the quiz.")

@socketio.on('disconnect')
def on_leave():
    if request.sid in participants:
        username = participants[request.sid]["username"]
        leave_room('quiz')
        del participants[request.sid]
        emit('update_participants', {"participants": participants, "count": len(participants)}, room='quiz')
        print(f"{username} left the quiz.")

@socketio.on('load_quiz')
def load_quiz(data):
    global selected_questions, current_question
    exam_name = data['exam_name']
    start_question = data.get('start_question', 1) - 1  # Default to question 1 if not provided
    selected_questions = backend.select_exam(exam_name)
    if selected_questions:
        num_questions = len(selected_questions)
        current_question['index'] = start_question  # Set the starting question index
        emit('quiz_loaded', {"success": True, "num_questions": num_questions, "start_question": start_question + 1}, room=request.sid)
    else:
        emit('quiz_loaded', {"success": False}, room=request.sid)

@socketio.on('start_quiz')
def start_quiz():
    if participants and selected_questions:
        current_question['started'] = True
        index = current_question['index']
        question = selected_questions[index]
        # Send the starting question to all clients
        emit('new_question', {"question": question["question"], "options": question["options"], "index": index + 1}, room='quiz')
        emit('enable_end_quiz', room=request.sid)  # Enable "End Quiz" for the host




@socketio.on('restart_quiz')
def restart_quiz():
    reset_quiz()
    emit('quiz_reset', room='quiz')
    start_quiz()

@socketio.on('submit_answer')
def receive_answer(data):
    username = participants[request.sid]["username"]
    answer = data['answer']
    current_question['answers'][username] = answer
    print(f"{username} submitted an answer: {answer}")

@socketio.on('check_answers')
def check_answers():
    index = current_question['index']
    if index < len(selected_questions):
        question = selected_questions[index]
        correct_answer = question['correct']
        results = {
            "question": question["question"],
            "answers": current_question["answers"],
            "correct_answer": correct_answer
        }

        chart_base64 = generate_chart(current_question["answers"], question["options"])
        emit('display_results', {"results": results, "chart": chart_base64}, room='quiz')

        for sid, participant in participants.items():
            if current_question['answers'].get(participant["username"]) == correct_answer:
                participants[sid]["score"] += 1

@socketio.on('next_question')
def next_question():
    current_question['index'] += 1
    current_question['answers'] = {}
    if current_question['index'] < len(selected_questions):
        question = selected_questions[current_question['index']]
        emit('clear_results', room='quiz')
        emit('new_question', {"question": question["question"], "options": question["options"], "index": current_question['index'] + 1}, room='quiz')
    else:
        final_results = calculate_final_results()
        emit('display_final_results', final_results, room='quiz')


@socketio.on('end_quiz')
def end_quiz():
    if current_question['started']:  # Ensure the quiz has started before ending it
        final_results = calculate_final_results()
        emit('display_final_results', final_results, room='quiz')
        reset_quiz()  # Reset the quiz state


def generate_chart(answers, options):
    letters = [chr(65 + i) for i in range(len(options))] # Dynamically generate letters for options
    counts = [list(answers.values()).count(option) for option in options]
    plt.figure(figsize=(6, 4))
    plt.bar(letters, counts)
    plt.xlabel('Options')
    plt.ylabel('Number of Votes')
    plt.title('Results')
    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    chart_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    plt.close()
    return chart_base64

def calculate_final_results():
    sorted_scores = sorted(participants.values(), key=lambda x: x['score'], reverse=True)
    return [{"username": p["username"], "score": p["score"]} for p in sorted_scores]

def reset_quiz():
    global selected_questions, current_question
    current_question = {"index": 0, "answers": {}, "started": False}
    for participant in participants.values():
        participant["score"] = 0

# if __name__ == '__main__':
#     print("Starting Real-Time Quiz Application...")
#     socketio.run(app, host='0.0.0.0', port=7860, debug=False)