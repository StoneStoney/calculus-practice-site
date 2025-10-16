import re
import json
from flask import Flask, render_template, jsonify
import os

app = Flask(__name__)

#==============================================================================
# PARSER 1: For the original '\begin{problem}' format (Unchanged)
# This is used for General_Derivative.txt
#==============================================================================
def find_balanced_content(text, start_index):
    if start_index >= len(text) or text[start_index] != '{':
        return None, -1
    brace_level = 1
    current_index = start_index + 1
    while current_index < len(text):
        char = text[current_index]
        if char == '{':
            brace_level += 1
        elif char == '}':
            brace_level -= 1
        if brace_level == 0:
            return text[start_index + 1 : current_index], current_index + 1
        current_index += 1
    return None, -1

def parse_latex_problem_format(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return {"error": f"The problem file '{os.path.basename(file_path)}' was not found on the server."}
    problem_start_regex = re.compile(r'\\begin{problem}')
    grouped_problems = {}
    current_pos = 0
    while True:
        match = problem_start_regex.search(content, current_pos)
        if not match:
            break
        brace1_start = match.end()
        category_raw, after_category_pos = find_balanced_content(content, brace1_start)
        if category_raw is None:
            current_pos = match.end() + 1
            continue
        brace2_start = after_category_pos
        problem_statement_raw, after_problem_statement_pos = find_balanced_content(content, brace2_start)
        if problem_statement_raw is None:
            current_pos = after_category_pos + 1
            continue
        category = category_raw.strip()
        problem_statement = problem_statement_raw.strip()
        end_problem_match = re.search(r'\\end{problem}', content[after_problem_statement_pos:], re.DOTALL)
        if not end_problem_match:
            current_pos = after_problem_statement_pos + 1
            continue
        inner_content_start = after_problem_statement_pos
        inner_content = content[inner_content_start : inner_content_start + end_problem_match.start()]
        hint, solution, answer = '', '', ''
        hint_start_tag = r'\hint{'
        hint_pos = inner_content.find(hint_start_tag)
        if hint_pos != -1:
            content_start = hint_pos + len(hint_start_tag)
            hint_text, _ = find_balanced_content(inner_content, content_start - 1)
            if hint_text is not None:
                hint = hint_text.strip()
        solution_start_tag = r'\solution{'
        solution_pos = inner_content.find(solution_start_tag)
        if solution_pos != -1:
            content_start = solution_pos + len(solution_start_tag)
            solution_text, _ = find_balanced_content(inner_content, content_start - 1)
            if solution_text is not None:
                solution = solution_text.strip()
        answer_start_tag = r'\answer{'
        answer_pos = inner_content.find(answer_start_tag)
        if answer_pos != -1:
            content_start = answer_pos + len(answer_start_tag)
            answer_text, _ = find_balanced_content(inner_content, content_start - 1)
            if answer_text is not None:
                answer = answer_text.strip()
        if not answer and solution:
             answer = solution
        if category not in grouped_problems:
            grouped_problems[category] = []
        grouped_problems[category].append({
            'problem': problem_statement,
            'hint': hint,
            'solution': solution,
            'answer': answer
        })
        current_pos = inner_content_start + end_problem_match.end()
    category_map = { 'By Definition of Derivative': 'Basic Differentiation', 'Basic Differentiation Identities': 'Basic Differentiation', 'Power Rule + e^x': 'Basic Differentiation', 'Derivatives of the Form a^x': 'Basic Differentiation', 'Trig Simplification': 'Trig Review', 'Product and Quotient Rule': 'Product, Quotient, & Chain Rules', 'Easy Chain Rule': 'Product, Quotient, & Chain Rules', 'Slightly Harder Chain Rule': 'Product, Quotient, & Chain Rules', 'QUICK TRIG': 'Trig Identities', 'Trig Identities - Easy': 'Trig Identities', 'Trig Identities - Medium': 'Trig Identities', 'Trig Identities - Hard': 'Trig Identities', 'Trig Identities - Harder': 'Trig Identities', 'haha good luck': 'General Review', "I'm sorry in advance": 'General Review', 'Summary (Easy)': 'General Review', 'Summary (Medium)': 'General Review', 'More General Practice': 'General Review', 'Pretty Hard': 'General Review', 'Yay Good luck': 'General Review' }
    super_category_order = [ 'Basic Differentiation', 'Trig Review', 'Product, Quotient, & Chain Rules', 'Trig Identities', 'General Review' ]
    final_grouped_problems = {name: [] for name in super_category_order}
    should_map_categories = os.path.basename(file_path) == 'General_Derivative.txt'
    if should_map_categories:
        for original_cat, problems_list in grouped_problems.items():
            super_cat_name = category_map.get(original_cat)
            if super_cat_name:
                final_grouped_problems[super_cat_name].extend(problems_list)
            else:
                print(f"Warning: Original category '{original_cat}' has no mapping and will be ignored.")
        output_list = []
        for super_cat_name, problems_list in final_grouped_problems.items():
            if problems_list:
                output_list.append({ 'category': super_cat_name, 'problems': problems_list })
    else:
        output_list = [{'category': cat, 'problems': prob_list} for cat, prob_list in grouped_problems.items()]
    return output_list

#==============================================================================
# PARSER 2: NEW parser for the '\begin{enumerate}' format
# This will be used for bigquiz2.txt
#==============================================================================
def parse_enumerate_format(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return {"error": f"The problem file '{os.path.basename(file_path)}' was not found on the server."}

    # The entire file will be one category, taken from the \section*{...} tag
    category_match = re.search(r'\\section\*\{([^}]+)\}', content)
    category = category_match.group(1).strip() if category_match else "Quiz Problems"

    problems = []
    
    # Split the content by \item, which separates each problem
    # We ignore the first split as it's the content before the first \item
    problem_blocks = content.split('\\item')[1:]

    for block in problem_blocks:
        # The problem statement is the first line
        problem_statement = block.split(r'\par')[0].strip()

        # Helper function to extract content using regex
        def extract_field(pattern, text):
            # This regex looks for the pattern (e.g., \textbf{Answer:}) and captures everything
            # until the next \par or the end of the enumerate block.
            match = re.search(pattern, text, re.DOTALL)
            return match.group(1).strip() if match else ''

        # Extract answer, solution, and hint
        answer = extract_field(r'\\textbf{Answer:}(.*?)(?=\\par|\\end{enumerate})', block)
        solution = extract_field(r'\\textbf{Solution:}(.*?)(?=\\par|\\end{enumerate})', block)
        hint = extract_field(r'\\textbf{Hint:}(.*?)(?=\\par|\\end{enumerate})', block)
        
        # If no separate answer is found, use the solution as the answer
        if not answer and solution:
            answer = solution
            
        problems.append({
            'problem': problem_statement,
            'hint': hint,
            'solution': solution,
            'answer': answer
        })

    # The final output must match the structure your JavaScript expects: a list of category dictionaries
    if not problems:
        return [] # Return empty list if no problems were parsed
        
    return [{'category': category, 'problems': problems}]

#==============================================================================
# FLASK ROUTES (Updated to choose the correct parser)
#==============================================================================
@app.route('/')
def home():
    return "<h1>Calculus Practice Site</h1><a href='/practice'>Go to Practice Page</a>"

@app.route('/practice')
def practice():
    return render_template('practice.html')

# --- THE ONE AND ONLY ROUTE FOR GETTING PROBLEMS ---
# This single route will now handle ALL problem files by choosing the right parser.
@app.route('/get-problems/<filename>')
def get_problems_from_file(filename):
    if '..' in filename or filename.startswith('/'):
        return jsonify({"error": "Invalid filename."}), 400

    file_path = f"{filename}.txt"
    problems_data = None # Initialize to None
    
    # --- DISPATCHER: Choose the correct parser based on the filename ---
    if filename == 'General_Derivative':
        print(f"Using 'problem' format parser for {filename}")
        problems_data = parse_latex_problem_format(file_path)
    elif filename == 'bigquiz2':
        print(f"Using 'enumerate' format parser for {filename}")
        problems_data = parse_enumerate_format(file_path)
    # You can add more files with custom formats here
    # elif filename == 'final_review':
    #     problems_data = parse_final_review_format(file_path)
    else:
        # A sensible default for any other files you might add
        print(f"Warning: No specific parser for '{filename}'. Using default 'problem' parser.")
        problems_data = parse_latex_problem_format(file_path)

    # Check if the parser returned a file-not-found error
    if isinstance(problems_data, dict) and "error" in problems_data:
        return jsonify(problems_data), 404
    
    # If parser found no problems but no error, return an empty list
    if problems_data is None:
        return jsonify([])
    
    return jsonify(problems_data)

if __name__ == '__main__':
    app.run(debug=True)