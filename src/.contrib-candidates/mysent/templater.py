import chevron


def markdown_escape(string):
    markdown_codes = {
        '*': '\\*',
        '_': '\\_',
        '`': '\\`',
        '[': '\\[',
    }
    for char in markdown_codes:
        string = string.replace(char, markdown_codes[char])
    return string


def render_chevron_template(template: str, context: dict) -> str:
    chevron.renderer._html_escape = markdown_escape
    return chevron.render(template, context)
