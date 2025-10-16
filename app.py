import re
import json
from flask import Flask, render_template, jsonify
import os

app = Flask(__name__)

#==============================================================================
# YOUR LATEX PARSER (Unchanged, it's perfect)
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

def parse_latex(file_path):
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
# FLASK ROUTES
#==============================================================================
@app.route('/')
def home():
    return "<h1>Calculus Practice Site</h1><a href='/practice'>Go to Practice Page</a>"

@app.route('/practice')
def practice():
    return render_template('practice.html')

# --- THE ONE AND ONLY ROUTE FOR GETTING PROBLEMS ---
# This single route will now handle ALL problem files using your parser.
@app.route('/get-problems/<filename>')
def get_problems_from_file(filename):
    if '..' in filename or filename.startswith('/'):
        return jsonify({"error": "Invalid filename."}), 400

    file_path = f"{filename}.txt"
    
    # ALWAYS use the parser. No more special cases.
    problems_data = parse_latex(file_path)

    # Check if the parser returned a file-not-found error
    if isinstance(problems_data, dict) and "error" in problems_data:
        return jsonify(problems_data), 404
    
    return jsonify(problems_data)

if __name__ == '__main__':
    app.run(debug=True)