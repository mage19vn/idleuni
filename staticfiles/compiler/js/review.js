// ==========================================
// KHỞI TẠO MONACO EDITOR TRONG CHẾ ĐỘ READ-ONLY
// ==========================================
let monacoEditor = null;

function initReviewEditor(codeContent, snippetLang) {
    require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.46.0/min/vs' }});
    require(['vs/editor/editor.main'], function() {
        monaco.editor.defineTheme('unicorns-dark', {
            base: 'vs-dark', inherit: true, rules: [],
            colors: { 'editor.background': '#181926', 'editorLineNumber.foreground': '#475569' }
        });
        monaco.editor.defineTheme('unicorns-light', {
            base: 'vs', inherit: true, rules: [],
            colors: { 'editor.background': '#f3f0ea', 'editorLineNumber.foreground': '#94a3b8' }
        });

        const isDark = document.body.classList.contains('dark-theme');
        let monacoTheme = localStorage.getItem('editor_theme');
        if (!monacoTheme || monacoTheme.startsWith('unicorns-')) {
            monacoTheme = isDark ? 'unicorns-dark' : 'unicorns-light';
        }
        const monacoFontSize = parseInt(localStorage.getItem('editor_font_size')) || 14;
        const monacoFontFamily = localStorage.getItem('editor_font_family') || "'Consolas', 'Fira Code', monospace";
        
        monacoEditor = monaco.editor.create(document.getElementById('editorContainer'), {
            value: codeContent,
            language: snippetLang === 'cpp' ? 'cpp' : 'python',
            theme: monacoTheme,
            automaticLayout: true,
            minimap: { enabled: false },
            fontSize: monacoFontSize,
            fontFamily: monacoFontFamily,
            scrollBeyondLastLine: false,
            padding: { top: 15 },
            readOnly: true
        });
    });
}

// Resizer Logic
const resizer = document.getElementById('resizer');
const leftPane = document.getElementById('leftPane');
const rightPane = document.getElementById('rightPane');

let x = 0;
let leftWidth = 0;

const mouseMoveHandler = function (e) {
    const dx = e.clientX - x;
    const containerWidth = resizer.parentNode.getBoundingClientRect().width;
    let newLeftWidth = ((leftWidth + dx) * 100) / containerWidth;
    
    if (newLeftWidth < 40) newLeftWidth = 40;
    if (newLeftWidth > 90) newLeftWidth = 90;

    leftPane.style.flex = `0 0 ${newLeftWidth}%`;
};

const mouseDownHandler = function (e) {
    x = e.clientX;
    const containerWidth = resizer.parentNode.getBoundingClientRect().width;
    leftWidth = leftPane.getBoundingClientRect().width;
    
    document.addEventListener('mousemove', mouseMoveHandler);
    document.addEventListener('mouseup', mouseUpHandler);
    resizer.classList.add('resizer-active');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
};

const mouseUpHandler = function () {
    document.removeEventListener('mousemove', mouseMoveHandler);
    document.removeEventListener('mouseup', mouseUpHandler);
    resizer.classList.remove('resizer-active');
    
    document.body.style.cursor = 'default';
    document.body.style.userSelect = '';
    
    if (monacoEditor) monacoEditor.layout();
};

if(resizer) resizer.addEventListener('mousedown', mouseDownHandler);


function copyReviewCode(btn) {
    if(typeof monacoEditor !== 'undefined' && monacoEditor) {
        const text = monacoEditor.getValue();
        const success = () => {
            const icon = btn.querySelector('i');
            if(icon) {
                icon.className = 'ph-bold ph-check';
                icon.style.color = '#22c55e';
                setTimeout(() => {
                    icon.className = 'ph-bold ph-copy';
                    icon.style.color = '';
                }, 2000);
            }
        };
        if(navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(text).then(success);
        } else {
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            textArea.style.top = '-999999px';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {
                document.execCommand('copy');
                success();
            } catch (err) {
                console.error('Fallback copy failed', err);
            }
            textArea.remove();
        }
    }
}
