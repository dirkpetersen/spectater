import os
import random
from flask import Flask, render_template, request, session, redirect, url_for

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.secret_key = os.urandom(24)  # For session management

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'target_number' not in session:
        session['target_number'] = random.randint(1, 100)
        session['attempts'] = 0
        session['game_over'] = False
        session['message'] = "I'm thinking of a number between 1 and 100. Can you guess it?"
    
    if request.method == 'POST':
        if session['game_over']:
            # Start a new game
            session.pop('target_number', None)
            session.pop('attempts', None)
            session.pop('game_over', None)
            session.pop('message', None)
            return redirect(url_for('index'))
        
        try:
            guess = int(request.form.get('guess', 0))
            session['attempts'] += 1
            
            if guess < session['target_number']:
                session['message'] = f"Too low! Try again. (Attempt {session['attempts']})"
            elif guess > session['target_number']:
                session['message'] = f"Too high! Try again. (Attempt {session['attempts']})"
            else:
                session['message'] = f"Congratulations! You guessed the number in {session['attempts']} attempts!"
                session['game_over'] = True
        except ValueError:
            session['message'] = "Please enter a valid number."
    
    return render_template('game.html', 
                          message=session['message'], 
                          attempts=session['attempts'],
                          game_over=session.get('game_over', False))

@app.route('/reset', methods=['GET'])
def reset():
    session.pop('target_number', None)
    session.pop('attempts', None)
    session.pop('game_over', None)
    session.pop('message', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
