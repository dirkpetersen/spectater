import random

def number_guessing_game():
    """
    A simple number guessing game where the player tries to guess
    a random number between 1 and 100.
    """
    print("Welcome to the Number Guessing Game!")
    print("I'm thinking of a number between 1 and 100.")
    
    # Generate a random number between 1 and 100
    secret_number = random.randint(1, 100)
    attempts = 0
    max_attempts = 10
    
    while attempts < max_attempts:
        try:
            # Get the player's guess
            guess = int(input(f"Attempts left: {max_attempts - attempts}. Enter your guess: "))
            attempts += 1
            
            # Check the guess
            if guess < secret_number:
                print("Too low! Try a higher number.")
            elif guess > secret_number:
                print("Too high! Try a lower number.")
            else:
                print(f"Congratulations! You guessed the number in {attempts} attempts!")
                break
                
        except ValueError:
            print("Please enter a valid number.")
    
    if attempts >= max_attempts and guess != secret_number:
        print(f"Game over! You've used all {max_attempts} attempts.")
        print(f"The secret number was {secret_number}.")

if __name__ == "__main__":
    play_again = "y"
    while play_again.lower() == "y":
        number_guessing_game()
        play_again = input("Do you want to play again? (y/n): ")
    
    print("Thanks for playing!")
