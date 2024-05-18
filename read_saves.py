#!/usr/bin/env python3
import pickle

def read_pickle_file(file_path):
    try:
        with open(file_path, 'rb') as file:
            data = pickle.load(file)
            print(data)
    except FileNotFoundError:
        print(f"File not found: {file_path}")
    except pickle.UnpicklingError:
        print(f"Error unpickling the file: {file_path}")
    except Exception as e:
        print(f"An error occurred: {e}")

# Path to the pickle file
pickle_file_path = 'data/state.pickle'

# Read and print the contents of the pickle file
read_pickle_file(pickle_file_path)
