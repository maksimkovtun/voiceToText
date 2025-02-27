from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from keras.models import load_model
from pydub import AudioSegment
import numpy as np
import librosa
import pyaudio
import uuid
import wave
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['SECRET_KEY'] = '123'
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    questions = db.relationship('Question', backref='test', lazy=True, cascade="all, delete-orphan")

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    answers = db.relationship('Answer', backref='question', lazy=True, cascade="all, delete-orphan")
    correct_answer = db.relationship('CorrectAnswer', backref='question', lazy=True, cascade="all, delete-orphan")

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(255), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)

class CorrectAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    correct_option = db.Column(db.String(100), nullable=False)
    
class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    answers = db.relationship('UserAnswer', backref='result', lazy=True, cascade="all, delete-orphan")

class UserAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey('result.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    selected_answer = db.Column(db.String(255), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def navig_links_ret():
    nav_links = []
    if current_user.is_authenticated:
        if current_user.is_admin:
            nav_links.append(('Главная', url_for('index')))
            nav_links.append(('Тесты', url_for('tests')))
            nav_links.append(('Результаты', url_for('results')))
            nav_links.append(('Результаты пользователей', url_for('admin_results')))
            nav_links.append(('Редактировать тесты', url_for('edit_tests')))
            nav_links.append(('Редактировать пользователей', url_for('admin_users')))
            nav_links.append(('Тест модели', url_for('neural_network_test')))
        else:
            nav_links.append(('Главная', url_for('index')))
            nav_links.append(('Тесты', url_for('tests')))
            nav_links.append(('Результаты', url_for('results')))
            nav_links.append(('О проекте', url_for('about')))
            nav_links.append(('Контакты', url_for('contact')))
    else:
        nav_links.append(('Главная', url_for('index')))
        nav_links.append(('Тесты', url_for('tests')))
        nav_links.append(('О проекте', url_for('about')))
        nav_links.append(('Контакты', url_for('contact')))
    return nav_links

@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
def admin_users():
    nav_links = navig_links_ret()
    error_message = None
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        user = User.query.filter_by(username=username).first()
        if user:
            return redirect(url_for('edit_user', user_id=user.id))
        else:
            error_message = 'Пользователь не найден'
    return render_template('admin_users.html', nav_links=nav_links, error_message=error_message)

@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('index'))
    user = User.query.get(user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('admin_users'))
    if request.method == 'POST':
        user.username = request.form['username']
        new_password = request.form['password']
        if new_password:
            user.password = generate_password_hash(new_password)
        is_admin = request.form.get('is_admin')
        user.is_admin = is_admin == 'on'
        db.session.commit()
        flash('User data successfully updated', 'success')
        return redirect(url_for('admin_users'))
    return render_template('edit_user.html', user=user)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully', 'success')
    return redirect(url_for('admin_users'))

@app.route('/')
def index():
    nav_links = navig_links_ret()
    return render_template('index.html', nav_links=nav_links)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            flash('You were successfully logged in.', 'success')
            return redirect(url_for('index'))
        else:
            error = 'Invalid username or password.'
            flash(error, 'error')
    return redirect(url_for('index'))

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    nav_links = navig_links_ret()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if not User.query.filter_by(username=username).first():
            new_user = User(username=username, password=generate_password_hash(password))
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username already exists. Please choose a different one.', 'error')
    return render_template('index.html', nav_links=nav_links)

@app.route('/tests')
def tests():
    nav_links = navig_links_ret()
    tests = Test.query.all()
    return render_template('tests.html', nav_links=nav_links, tests=tests)
    
@app.route('/tests/<int:test_id>')
def show_test(test_id):
    nav_links = navig_links_ret()
    test = Test.query.get(test_id)
    if test:
        return render_template('test.html', nav_links=nav_links, title='Test', test=test)
    else:
        return 'Test not found', 404

@app.route('/tests/<int:test_id>/next_question', methods=['POST'])
def get_next_question(test_id):
    current_question_index = request.json.get('current_question_index', 0)
    current_question_index += 1  

    test = Test.query.get(test_id)
    next_question = None
    if test:
        next_question = test.questions[current_question_index] if current_question_index < len(test.questions) else None
    
    if next_question:
        is_last_question = current_question_index == len(test.questions) - 1 
        return jsonify({
            'success': True,
            'question_content': next_question.content,
            'answers': [answer.content for answer in next_question.answers],
            'is_last_question': is_last_question 
        })
    else:
        return jsonify({'success': False, 'message': 'No more questions'})

@app.route('/tests/<int:test_id>/finish', methods=['POST'])
@login_required
def finish_test(test_id):
    test = Test.query.get(test_id)
    if not test:
        return 'Test not found', 404

    user_answers = request.json.get('user_answers', [])

    result = Result(test_id=test_id, user_id=current_user.id)
    db.session.add(result)
    db.session.commit()

    print("User answers:")
    for answer_data in user_answers:
        question_id = answer_data.get('question_id')
        selected_answer = answer_data.get('selected_answer')
        print(f"Question ID: {question_id}, Selected answer: {selected_answer}")

        user_answer = UserAnswer(result_id=result.id, question_id=question_id, selected_answer=selected_answer)
        db.session.add(user_answer)

    db.session.commit()

    return redirect(url_for('results')) 

@app.route('/admin/results', methods=['GET', 'POST'])
@login_required
def admin_results():
    nav_links = navig_links_ret()
    error_message = None
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        user = User.query.filter_by(username=username).first()
        if user:
            return redirect(url_for('admin_result', user_id=user.id))
        else:
            error_message = 'Пользователь не найден'
    return render_template('admin_results.html', nav_links=nav_links, error_message=error_message)

@app.route('/admin/results/<int:user_id>')
@login_required
def admin_result(user_id):
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('index'))
    nav_links = navig_links_ret()
    user_results = Result.query.filter_by(user_id=user_id).all()
    
    for result in user_results:
        result.test = Test.query.get(result.test_id)
        correct_answers = 0

        user_answers = UserAnswer.query.filter_by(result_id=result.id).all()

        print("User Answers:")
        for user_answer in user_answers:
            print(f"Result ID: {user_answer.result_id}, Question ID: {user_answer.question_id}, Selected Answer: {user_answer.selected_answer}")

        questions = Question.query.filter_by(test_id=result.test_id).all()
        
        for question in questions:
            print(f"Question: {question.content}")

            correct_answer = CorrectAnswer.query.filter_by(question_id=question.id).first()
            if correct_answer:
                print(f"Correct answer: {correct_answer.correct_option}")
            else:
                print("No correct answer found for question.")

            selected_answer_text = None
            for user_answer in user_answers:
                corresponding_question = Question.query.filter_by(test_id=result.test_id).order_by(Question.id).offset(user_answer.question_id).first()
                if corresponding_question:
                    if corresponding_question.id == question.id:
                        selected_answer_text = user_answer.selected_answer
                        break
            
            print(f"Selected answer: {selected_answer_text}")

            if str(selected_answer_text).strip() == str(correct_answer.correct_option).strip():
                correct_answers += 1
        
        result.correct_answers = correct_answers
        print(f"Result: {result.test.title}, Correct Answers: {correct_answers}")

    return render_template('results.html', nav_links=nav_links, user_results=user_results, user_id=user_id)

@app.route('/results')
@login_required
def results():
    nav_links = navig_links_ret()
    user_results = Result.query.filter_by(user_id=current_user.id).all()
    
    for result in user_results:
        result.test = Test.query.get(result.test_id)
        correct_answers = 0

        user_answers = UserAnswer.query.filter_by(result_id=result.id).all()

        print("User Answers:")
        for user_answer in user_answers:
            print(f"Result ID: {user_answer.result_id}, Question ID: {user_answer.question_id}, Selected Answer: {user_answer.selected_answer}")

        questions = Question.query.filter_by(test_id=result.test_id).all()
        
        for question in questions:
            print(f"Question: {question.content}")

            correct_answer = CorrectAnswer.query.filter_by(question_id=question.id).first()
            if correct_answer:
                print(f"Correct answer: {correct_answer.correct_option}")
            else:
                print("No correct answer found for question.")

            selected_answer_text = None
            for user_answer in user_answers:
                corresponding_question = Question.query.filter_by(test_id=result.test_id).order_by(Question.id).offset(user_answer.question_id).first()
                if corresponding_question:
                    if corresponding_question.id == question.id:
                        selected_answer_text = user_answer.selected_answer
                        break
            
            print(f"Selected answer: {selected_answer_text}")

            if str(selected_answer_text).strip() == str(correct_answer.correct_option).strip():
                correct_answers += 1
        
        result.correct_answers = correct_answers
        print(f"Result: {result.test.title}, Correct Answers: {correct_answers}")

    return render_template('results.html', nav_links=nav_links, user_results=user_results, user_id=current_user.id)
    
@app.route('/results/<int:result_id>')
@login_required
def detailed_results(result_id):
    nav_links = navig_links_ret()
    result = Result.query.get_or_404(result_id)

    user_answers = UserAnswer.query.filter_by(result_id=result.id).all()

    result.test = Test.query.get(result.test_id)

    correct_answers = []
    user_selected_answers = []

    for idx, question in enumerate(result.test.questions):
        correct_answer = CorrectAnswer.query.filter_by(question_id=question.id).first()
        correct_option = correct_answer.correct_option if correct_answer else "No correct option found"
        correct_answers.append(correct_option)

        if idx < len(user_answers):
            user_answer = user_answers[idx].selected_answer
        else:
            user_answer = "Без ответа"
        user_selected_answers.append(user_answer)

    return render_template('detailed_results.html', nav_links=nav_links, result=result, correct_answers=correct_answers, user_selected_answers=user_selected_answers)

@app.route('/admin/delete_all_results', methods=['POST'])
@login_required
def delete_all_results():
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('index'))

    Result.query.delete()
    db.session.commit()

    flash('All results deleted successfully', 'success')
    return redirect(url_for('admin_results'))

@app.route('/admin/results/<int:user_id>/<int:result_id>/delete', methods=['POST'])
@login_required
def delete_result(user_id, result_id):
    if not current_user.is_admin:
        flash('У вас нет прав для выполнения этой операции', 'error')
        return redirect(url_for('index'))
    
    result = Result.query.get_or_404(result_id)
    db.session.delete(result)
    db.session.commit()
    flash('Результат успешно удален', 'success')
    return redirect(url_for('admin_result', user_id=user_id))

@app.route('/edit_tests')
@login_required
def edit_tests():
    nav_links = navig_links_ret()
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('index'))
    tests = Test.query.all()
    return render_template('edit_tests.html', nav_links=nav_links, tests=tests)

@app.route('/edit_tests/<int:test_id>', methods=['GET', 'POST'])
@login_required
def edit_test(test_id):
    nav_links = navig_links_ret()
    if not current_user.is_admin:
        flash('You do not have permission to access this page', 'error')
        return redirect(url_for('index'))
    
    test = Test.query.get_or_404(test_id)
    
    if request.method == 'POST':
        test.title = request.form['title']
        test.description = request.form['description']

        for question in test.questions:
            question.content = request.form.get(f'question{question.id}', '')

            correct_option = request.form.get(f'correct_answer_{question.id}')

            if correct_option: 
                correct_answer = CorrectAnswer.query.filter_by(question_id=question.id).first()
                if correct_answer:
                    correct_answer.correct_option = correct_option
                else:
                    correct_answer = CorrectAnswer(question_id=question.id, correct_option=correct_option)
                    db.session.add(correct_answer)

            for answer in question.answers:
                answer_content = request.form.get(f'answer{answer.id}') 
                answer.content = answer_content 

        db.session.commit()
        flash('Test and questions updated successfully', 'success')
        return redirect(url_for('edit_tests'))
    
    return render_template('edit_test.html', nav_links=nav_links, test=test, get_correct_answer=get_correct_answer)

def get_correct_answer(question_id):
    correct_answer = CorrectAnswer.query.filter_by(question_id=question_id).first()
    return str(correct_answer.correct_option) if correct_answer else ''

@app.route('/add_tests', methods=['GET', 'POST'])
def add_tests():
    nav_links = navig_links_ret()
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        new_test = Test(title=title, description=description)
        db.session.add(new_test)
        db.session.commit()

        question_contents = request.form.getlist('question_content')[1:]  
        answers = request.form.getlist('answers[]')[6:]  
        cor_answers = request.form.getlist('correct_answer')[1:] 

        for i, content in enumerate(question_contents):
            new_question = Question(content=content, test_id=new_test.id)
            db.session.add(new_question)
            db.session.flush() 
            print("Question ID:", new_question.id)
            print("Correct Answer:", cor_answers[i] if i < len(cor_answers) else None)

            for j, answer_content in enumerate(answers[i*6:(i+1)*6]):  
                if answer_content:  
                    is_correct = answer_content == cor_answers[i]  
                    new_answer = Answer(content=answer_content, question_id=new_question.id)
                    db.session.add(new_answer)

                    if is_correct:
                        correct_answer = CorrectAnswer(question_id=new_question.id, correct_option=answer_content)  
                        db.session.add(correct_answer)

        db.session.commit()

        flash('Test added successfully', 'success')
        return redirect(url_for('tests'))
    return render_template('add_tests.html', nav_links=nav_links)

@app.route('/delete_test/<int:test_id>', methods=['POST'])
def delete_test(test_id):
    test = Test.query.get_or_404(test_id)
    db.session.delete(test)
    db.session.commit()
    flash('Test deleted successfully', 'success')
    return redirect(url_for('edit_tests'))

@app.route('/about')
def about():
    nav_links = navig_links_ret()
    return render_template('about.html', nav_links=nav_links)

@app.route('/contact')
def contact():
    nav_links = navig_links_ret()
    return render_template('contact.html', nav_links=nav_links)

class VoiceTestApp:
    def __init__(self):
        self.model_path = './templates/my_model_rus_eng.h5'
        self.loaded_model = None
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        self.RECORD_SECONDS = 2
        self.p = pyaudio.PyAudio()
        self.stream = None

    def load_model(self):
        if self.loaded_model is None:
            self.loaded_model = load_model(self.model_path)
            
    def predict_voice(self, input_data):
        input_data = np.expand_dims(input_data, axis=0)
        predictions = self.loaded_model.predict(input_data)
        predicted_class = np.argmax(predictions)
        return predicted_class

    def record_audio(self):
        frames = []
        self.stream = self.p.open(format=self.FORMAT,
                                  channels=self.CHANNELS,
                                  rate=self.RATE,
                                  input=True,
                                  frames_per_buffer=self.CHUNK)
        for i in range(int(self.RATE / self.CHUNK * self.RECORD_SECONDS)):
            data = self.stream.read(self.CHUNK)
            frames.append(data)
        self.stream.stop_stream()
        self.stream.close()
        return frames

    def save_and_process_audio(self, frames):
        file_path = "temp.wav"
        wf = wave.open(file_path, 'wb')
        wf.setnchannels(self.CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(self.RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        Y, sr = librosa.load(file_path)
        input_data = librosa.feature.mfcc(y=Y, sr=sr)
        predicted_class = self.predict_voice(input_data)
        class_mapping = {0: 'Один', 1: 'Два', 2: 'Три', 3: 'Четыре', 4: 'Пять', 5: 'Шесть'}
        predicted_class_name = class_mapping[predicted_class]
 
        return jsonify({"message": "Audio recorded and processed successfully", "predicted_class": predicted_class_name})


voice_test_app = VoiceTestApp()

@app.before_request
def load_voice_test_app():
    voice_test_app.load_model()

@app.route('/neural_network_test', methods=['GET', 'POST'])
def neural_network_test():
    nav_links = navig_links_ret()
    if request.method == 'GET':
        return render_template('neural_network_test.html', nav_links=nav_links)
    elif request.method == 'POST':
        return jsonify({'result': 'Processed result'})  

p = pyaudio.PyAudio()
  

@app.route('/record_audio', methods=['POST'])
def record_audio():
    frames = voice_test_app.record_audio()  
    result = voice_test_app.save_and_process_audio(frames)  
    
    print("Response data:", result)  
    
    return result
    
@app.route('/start_audio_recording', methods=['POST'])
def start_audio_recording():
    frames = voice_test_app.record_audio()  
    folder_name = request.json.get('folder_name') 
    lang = request.json.get('language')
    file_name = str(uuid.uuid4()) + '.wav'
    file_path = os.path.join('static/audio/', lang, folder_name, file_name)  
    wf = wave.open(file_path, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(16000)
    wf.writeframes(b''.join(frames)) 
    wf.close()

    folder_path = os.path.join('static/audio/', lang, folder_name)
    file_count = len(os.listdir(folder_path))

    return jsonify({'file_name': file_name, 'file_count': file_count}), 200
    

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        admin_user = User.query.filter_by(username='root').first()

        if not admin_user:
            admin_user = User(username='root', password=generate_password_hash('root'), is_admin=True)
            db.session.add(admin_user)
            db.session.commit()
    
    app.run(host='0.0.0.0', debug=True)