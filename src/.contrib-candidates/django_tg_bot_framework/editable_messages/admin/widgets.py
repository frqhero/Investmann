from django.contrib.admin import widgets


class MonacoEditorWidget(widgets.AdminTextareaWidget):
    template_name = 'admin/editable_messages/monaco_editor_widget.html'

    class Media:
        css = {
            'all': (
                'https://cdn.jsdelivr.net/npm/monaco-editor@0.41.0/dev/vs/editor/editor.main.min.css',
                'admin/editable_messages/monaco_editor_widget.css',
            ),
        }
