from jinja2 import Environment, FileSystemLoader
import datetime

env = Environment(loader=FileSystemLoader('templates'))
current_year = datetime.datetime.now().year

def generate_index():
    template = env.get_template('index.html')
    html = template.render(title='Home', current_year=current_year)
    with open('docs/index.html', 'w') as f:
        f.write(html)

def main():
    generate_index()
    # You can add other page generation functions here later

if __name__ == '__main__':
    main()
