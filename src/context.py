import os
import re

def format_context(filename, string):
    """
    Format the context by removing the file extension, replacing spaces and underscores with '-',
    and converting to lowercase.
    """
    base_name = os.path.splitext(filename)[0].replace(" ", "-").replace("_", "-").lower()  # Remove file extension
    formatted_string = string.replace(" ", "-").replace("_", "-").lower()
    return f"{base_name}-{formatted_string}"

def add_context_to_translate_tags(base_dir):
    """
    Traverse all files in the base directory, find {% translate %} tags,
    and add a formatted context.
    """
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".html"):  # Target only Django template files
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Regex to find {% translate %} tags
                translate_pattern = r"{%\s*translate\s+(['\"])(.*?)\1\s*%}"
                matches = re.finditer(translate_pattern, content)

                updated_content = content
                for match in matches:
                    original_tag = match.group(0)
                    string_to_translate = match.group(2)
                    context = format_context(file, string_to_translate)
                    new_tag = f"{{% translate '{string_to_translate}' context '{context}' %}}"
                    updated_content = updated_content.replace(original_tag, new_tag)

                # Write back the updated content if changes were made
                if content != updated_content:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(updated_content)
                    print(f"Updated file: {file_path}")

if __name__ == "__main__":
    # Replace with the path to your Django project templates directory
    templates_dir = r"c:\Users\alber\Git\quickstatements3\src\web\templates"
    add_context_to_translate_tags(templates_dir)