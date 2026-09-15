def fix_file():
    path = 'templates/dashboard.html'
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    start_marker = "/* IN JAVASCRIPT SECTION BELOW */"
    end_marker = "* {"
    
    start_idx = -1
    end_idx = -1
    
    for i, line in enumerate(lines):
        if start_marker in line:
            start_idx = i
        if end_marker in line and i > start_idx:
            end_idx = i
            break
            
    if start_idx != -1 and end_idx != -1:
        print(f"Removing lines {start_idx} to {end_idx}")
        # Keep lines before start and from end onwards
        new_lines = lines[:start_idx] + lines[end_idx:]
        
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print("File fixed.")
    else:
        print("Markers not found.")

if __name__ == "__main__":
    fix_file()
