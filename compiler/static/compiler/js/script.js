const consoleOutput = document.getElementById('consoleOutput');
const visualizerArea = document.getElementById('visualizerArea');
const runBtn = document.getElementById('runBtn');
const loader = document.getElementById('loader');
const langSelect = document.getElementById('langSelect');
const stdInput = document.getElementById('stdInput');

const debugModal = document.getElementById('debugModal');
const modalOverlay = document.getElementById('modalOverlay');
const debugList = document.getElementById('debugList');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');

const timeSlider = document.getElementById('timeSlider');
const stepCounter = document.getElementById('stepCounter');

let globalTraceData = [];
let globalOutput = "";
let currentStepIndex = 0;
let isDebugOpen = false;
let visibleVariables = new Set();
let currentErrorLine = -1;

let isVisualizerVisible = false;
let isPrevLineVisible = true;

// ==========================================
// XỬ LÝ THANH KÉO THẢ (RESIZER)
// ==========================================
const resizer = document.getElementById('resizer');
const leftPane = document.getElementById('leftPane');
const rightPane = document.getElementById('rightPane');

let x = 0;
let leftWidth = 0;

const mouseMoveHandler = function (e) {
    const dx = e.clientX - x;
    const containerWidth = resizer.parentNode.getBoundingClientRect().width;
    let newLeftWidth = ((leftWidth + dx) * 100) / containerWidth;
    
    if (newLeftWidth < 20) newLeftWidth = 20;
    if (newLeftWidth > 80) newLeftWidth = 80;

    leftPane.style.flex = `0 0 ${newLeftWidth}%`;
};

const mouseDownHandler = function (e) {
    x = e.clientX;
    const containerWidth = resizer.parentNode.getBoundingClientRect().width;
    leftWidth = leftPane.getBoundingClientRect().width;

    // Chốt cứng % hiện tại của bảng trái ngay khi click
    const currentPercent = (leftWidth / containerWidth) * 100;
    leftPane.style.flex = `0 0 ${currentPercent}%`;

    rightPane.style.flex = '1 1 0%'; 
    
    document.body.style.userSelect = 'none'; 
    document.body.style.pointerEvents = 'none';
    resizer.style.pointerEvents = 'auto'; 
    
    document.addEventListener('mousemove', mouseMoveHandler);
    document.addEventListener('mouseup', mouseUpHandler);
    resizer.classList.add('resizer-active');
    document.body.style.cursor = 'col-resize';
};

const mouseUpHandler = function () {
    document.removeEventListener('mousemove', mouseMoveHandler);
    document.removeEventListener('mouseup', mouseUpHandler);
    resizer.classList.remove('resizer-active');
    
    document.body.style.cursor = 'default';
    document.body.style.userSelect = '';
    document.body.style.pointerEvents = '';
    
    if (monacoEditor) monacoEditor.layout();
};

if(resizer) resizer.addEventListener('mousedown', mouseDownHandler);

// ==========================================
// XỬ LÝ CHUYỂN TAB TRÊN MOBILE
// ==========================================
function switchTab(tabName) {
    const leftP = document.getElementById('leftPane');
    const rightP = document.getElementById('rightPane');
    const editorC = document.getElementById('editorContainer');
    const ioW = document.getElementById('ioWrapper');
    const buttons = document.querySelectorAll('.tab-btn');

    leftP.style.display = 'none';
    rightP.style.display = 'none';
    buttons.forEach(b => b.classList.remove('active'));

    if (tabName === 'editor') {
        leftP.style.display = 'flex';
        editorC.style.display = 'block';
        ioW.style.display = 'none';
        buttons[0].classList.add('active');
    } else if (tabName === 'console') {
        leftP.style.display = 'flex';
        editorC.style.display = 'none';
        ioW.style.display = 'flex';
        buttons[1].classList.add('active');
    } else if (tabName === 'visualizer') {
        rightP.style.display = 'flex';
        buttons[2].classList.add('active');
    }
    
    if (monacoEditor) monacoEditor.layout();
}


// ==========================================
// 1. KHỞI TẠO MONACO EDITOR 
// ==========================================
let monacoEditor = null;
let lineDecorations = []; 

const defaultPython = `print("Chương trình tính tổng 2 số")\na = int(input())\nb = int(input())\ntong = a + b\nprint(f"Tổng là: {tong}")`;
const defaultCpp = `#include <iostream>\nusing namespace std;\n\nint TinhTong(int x, int y) {\n    return x + y;\n}\n\nint main() {\n    int a, b;\n    cin >> a >> b;\n    int tong = TinhTong(a, b);\n    cout << "Tong la: " << tong << endl;\n    return 0;\n}`;

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
    
    const initialLang = langSelect ? langSelect.value : 'python';
    const savedCode = localStorage.getItem('unicorns_code_' + initialLang);
    const savedInput = localStorage.getItem('unicorns_input_' + initialLang);
    
    const initialCode = window.initialSnippetCode ? window.initialSnippetCode : (savedCode ? savedCode : (initialLang === 'cpp' ? defaultCpp : defaultPython));
    if (window.initialSnippetLang) {
        if (langSelect) langSelect.value = window.initialSnippetLang;
    }
    
    let monacoTheme = localStorage.getItem('editor_theme');
    if (!monacoTheme || monacoTheme.startsWith('unicorns-')) {
        monacoTheme = isDark ? 'unicorns-dark' : 'unicorns-light';
    }
    const monacoFontSize = parseInt(localStorage.getItem('editor_font_size')) || 14;
    const monacoFontFamily = localStorage.getItem('editor_font_family') || "'Consolas', 'Fira Code', monospace";
    
    monacoEditor = monaco.editor.create(document.getElementById('editorDOM'), {
        value: initialCode,
        language: initialLang === 'cpp' ? 'cpp' : 'python',
        theme: monacoTheme,
        automaticLayout: true,
        minimap: { enabled: false },
        fontSize: monacoFontSize,
        fontFamily: monacoFontFamily,
        scrollBeyondLastLine: false,
        padding: { top: 15 }
    });

    if (stdInput) {
        if (window.initialSnippetInput) {
            stdInput.value = window.initialSnippetInput;
        } else if (savedInput !== null) {
            stdInput.value = savedInput;
        } else {
            stdInput.value = initialLang === 'cpp' ? "10 20" : "10\n20";
        }
    }

    monacoEditor.onDidChangeModelContent(() => {
        const currentLang = langSelect ? langSelect.value : 'python';
        localStorage.setItem('unicorns_code_' + currentLang, monacoEditor.getValue());
    });

    // --- CÀI ĐẶT SNIPPET TEMPLATES ---
    const defaultTemplates = [
        { name: "body", language: "cpp", code: "#include <iostream>\nusing namespace std;\n\nint main() {\n\t$1\n\treturn 0;\n}" },
        { name: "class", language: "cpp", code: "class $1 {\nprivate:\n\t$2\npublic:\n\t$1() {}\n\t~$1() {}\n};" },
        { name: "void", language: "cpp", code: "void $1($2) {\n\t$3\n}" },
        { name: "for", language: "cpp", code: "for(int ${1:i} = 0; ${1:i} < $2; ${1:i}++) {\n\t$3\n}" },
        { name: "body", language: "python", code: "def main():\n\t$1\n\nif __name__ == '__main__':\n\tmain()" },
        { name: "class", language: "python", code: "class $1:\n\tdef __init__(self):\n\t\t$2" },
        { name: "def", language: "python", code: "def $1($2):\n\t$3" },
        { name: "for", language: "python", code: "for ${1:i} in range($2):\n\t$3" },
    ];

    let userTemplates = [];
    const utElement = document.getElementById('user-templates-data');
    if (utElement) {
        try { userTemplates = JSON.parse(utElement.textContent); } catch(e) {}
    }

    window.availableTemplates = [...defaultTemplates];
    // Merge user templates (ghi đè mặc định nếu trùng tên + ngôn ngữ)
    if (Array.isArray(userTemplates)) {
        userTemplates.forEach(ut => {
            const idx = window.availableTemplates.findIndex(dt => dt.name === ut.name && (dt.language === ut.language || ut.language === 'all' || dt.language === 'all'));
            if (idx !== -1) window.availableTemplates[idx] = ut;
            else window.availableTemplates.push(ut);
        });
    }

    // Thêm action cho phím tắt mở Menu Template
    const scOpenTemplate = localStorage.getItem('sc_openTemplate') || 'Alt+J';
    let monacoKeyMod = 0;
    if (scOpenTemplate.includes('Ctrl')) monacoKeyMod |= monaco.KeyMod.CtrlCmd;
    if (scOpenTemplate.includes('Alt')) monacoKeyMod |= monaco.KeyMod.Alt;
    if (scOpenTemplate.includes('Shift')) monacoKeyMod |= monaco.KeyMod.Shift;
    
    let keyPart = scOpenTemplate.split('+').pop();
    let monacoKeyCode = monaco.KeyCode.Unknown;
    if (keyPart.length === 1 && keyPart >= 'A' && keyPart <= 'Z') {
        monacoKeyCode = monaco.KeyCode['Key' + keyPart];
    } else if (keyPart === 'Space') {
        monacoKeyCode = monaco.KeyCode.Space;
    } else {
        monacoKeyCode = monaco.KeyCode.KeyJ; // Fallback
    }

    monacoEditor.addAction({
        id: 'insert-snippet-template',
        label: 'Insert Template',
        keybindings: [monacoKeyMod | monacoKeyCode],
        run: function(ed) {
            showTemplateMenu(ed);
        }
    });

});

// --- HIỂN THỊ MENU TEMPLATES ---
function showTemplateMenu(ed) {
    console.log("Alt+J triggered!");
    const lang = langSelect ? langSelect.value : 'python';
    const templates = window.availableTemplates.filter(t => t.language === lang || t.language === 'all');
    console.log("Found templates:", templates);
    
    if (templates.length === 0) return;

    let menu = document.getElementById('template-suggest-menu');
    if (!menu) {
        menu = document.createElement('ul');
        menu.id = 'template-suggest-menu';
        menu.className = 'autocomplete-list';
        menu.style.zIndex = '99999';
        document.body.appendChild(menu);
    }
    
    menu.innerHTML = '';
    templates.forEach((t, i) => {
        const li = document.createElement('li');
        li.innerHTML = `<span class="suggest-icon icon-keyword">T</span> <span class="suggest-text">${t.name}</span>`;
        if (i === 0) li.classList.add('active');
        li.onclick = () => { insertTemplate(ed, t.code); menu.style.display = 'none'; };
        li.onmouseenter = () => {
            menu.querySelectorAll('li').forEach(el => el.classList.remove('active'));
            li.classList.add('active');
        };
        menu.appendChild(li);
    });

    // Lấy tọa độ con trỏ
    const pos = ed.getPosition();
    const cursorCoords = ed.getScrolledVisiblePosition(pos);
    const editorDom = ed.getDomNode();
    const rect = editorDom.getBoundingClientRect();
    
    if (cursorCoords) {
        menu.style.left = (rect.left + cursorCoords.left) + 'px';
        menu.style.top = (rect.top + cursorCoords.top + 20) + 'px'; // ngay dưới con trỏ
    } else {
        menu.style.left = rect.left + 'px';
        menu.style.top = rect.top + 'px';
    }
    menu.style.display = 'block';

    // Xử lý phím mũi tên và Enter
    const keydownHandler = function(e) {
        if (menu.style.display === 'none') {
            document.removeEventListener('keydown', keydownHandler, true);
            return;
        }
        const items = menu.querySelectorAll('li');
        let activeIdx = Array.from(items).findIndex(li => li.classList.contains('active'));
        
        if (e.key === 'ArrowDown') {
            e.preventDefault(); e.stopPropagation();
            if (activeIdx < items.length - 1) {
                items[activeIdx].classList.remove('active');
                items[activeIdx + 1].classList.add('active');
                items[activeIdx + 1].scrollIntoView({block: 'nearest'});
            }
        } else if (e.key === 'ArrowUp') {
            e.preventDefault(); e.stopPropagation();
            if (activeIdx > 0) {
                items[activeIdx].classList.remove('active');
                items[activeIdx - 1].classList.add('active');
                items[activeIdx - 1].scrollIntoView({block: 'nearest'});
            }
        } else if (e.key === 'Enter') {
            e.preventDefault(); e.stopPropagation();
            if (activeIdx >= 0) items[activeIdx].click();
        } else if (e.key === 'Escape') {
            e.preventDefault(); e.stopPropagation();
            menu.style.display = 'none';
        } else {
            // Đóng menu nếu gõ phím khác
            menu.style.display = 'none';
        }
    };
    
    // Xóa listener cũ nếu có, gán listener mới (dùng capture phase để ưu tiên)
    document.addEventListener('keydown', keydownHandler, true);
    
    // Đóng khi click ra ngoài
    const clickHandler = function(e) {
        if (!menu.contains(e.target)) {
            menu.style.display = 'none';
            document.removeEventListener('mousedown', clickHandler);
        }
    };
    document.addEventListener('mousedown', clickHandler);
}

function insertTemplate(ed, code) {
    ed.focus();
    try {
        // Cố gắng sử dụng SnippetController2 của Monaco (Hỗ trợ tốt các tab stop $1, $2)
        const contrib = ed.getContribution('snippetController2');
        if (contrib && typeof contrib.insert === 'function') {
            contrib.insert(code);
            return;
        }
    } catch (e) {}

    // Fallback: Chèn dạng text thô nếu không tìm thấy SnippetController
    const position = ed.getPosition();
    ed.executeEdits("snippet", [{
        range: new monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column),
        text: code
    }]);
}

if (stdInput) {
    stdInput.addEventListener('input', () => {
        const currentLang = langSelect ? langSelect.value : 'python';
        localStorage.setItem('unicorns_input_' + currentLang, stdInput.value);
    });
}

// ==========================================
// 2. GIAO DIỆN & CÀI ĐẶT
// ==========================================
const themeToggleBtn = document.getElementById('themeToggleBtn');
const savedTheme = localStorage.getItem('theme');
if (savedTheme === 'dark') {
    document.body.classList.add('dark-theme');
    if(themeToggleBtn) themeToggleBtn.innerText = '☀️'; 
}



function toggleVisualizer() {
    isVisualizerVisible = !isVisualizerVisible;
    const paneRight = document.querySelector('.pane-right');
    const workspace = document.querySelector('.workspace'); 
    const btnToggleVis = document.getElementById('btnToggleVis');
    const btnTogglePrev = document.getElementById('btnTogglePrev');
    
    const resizer = document.getElementById('resizer');
    const leftPane = document.getElementById('leftPane');

    if (isVisualizerVisible) {
        if(paneRight) paneRight.style.display = 'flex'; 
        if(workspace) workspace.classList.remove('hide-vis'); 
        if(btnToggleVis) btnToggleVis.innerHTML = '<i class="ph-bold ph-eye-slash"></i> Ẩn bảng Visualizer';
        if (isPrevLineVisible && btnTogglePrev) btnTogglePrev.classList.remove('disabled');
        
        if(resizer) resizer.style.display = 'flex';
        if(leftPane) leftPane.style.flex = ''; 
    } else {
        if(paneRight) paneRight.style.display = 'none'; 
        if(workspace) workspace.classList.add('hide-vis');
        if(btnToggleVis) btnToggleVis.innerHTML = '<i class="ph-bold ph-eye"></i> Hiện bảng Visualizer';
        if(btnTogglePrev) btnTogglePrev.classList.add('disabled');
        
        if(resizer) resizer.style.display = 'none';
        if(leftPane) leftPane.style.flex = '1 1 100%';
    }
    updateArrowPosition();
    
    if (monacoEditor) {
        setTimeout(() => monacoEditor.layout(), 50);
    }
}

function togglePrevLine() {
    if (!isVisualizerVisible) return; 
    isPrevLineVisible = !isPrevLineVisible;
    const btn = document.getElementById('btnTogglePrev');
    if(btn) isPrevLineVisible ? btn.classList.remove('disabled') : btn.classList.add('disabled');
    updateArrowPosition();
}

function toggleDebug() {
    isDebugOpen = !isDebugOpen;
    if(debugModal) debugModal.style.display = isDebugOpen ? 'block' : 'none';
    if(modalOverlay) modalOverlay.style.display = isDebugOpen ? 'block' : 'none';
}

function changeLanguage() {
    const lang = langSelect.value;
    const monacoLang = lang === 'cpp' ? 'cpp' : 'python';
    
    if (monacoEditor) {
        monaco.editor.setModelLanguage(monacoEditor.getModel(), monacoLang);
        
        const savedCode = localStorage.getItem('unicorns_code_' + lang);

        if (savedCode) {
            monacoEditor.setValue(savedCode);
        } else {
            if (lang === 'cpp') {
                monacoEditor.setValue(defaultCpp); 
                if(stdInput) stdInput.value = "10 20";
            } else if (lang === 'python') {
                monacoEditor.setValue(defaultPython);
                if(stdInput) stdInput.value = "10\n20";
            }
        }
    }
}

// ==========================================
// 3. LOGIC TRACE & GIAO TIẾP VỚI MONACO
// ==========================================
function updateArrowPosition() {
    if (!monacoEditor) return;
    
    let newDecorations = [];

    if (currentErrorLine > 0) {
        newDecorations.push({
            range: new monaco.Range(currentErrorLine, 1, currentErrorLine, 1),
            options: { 
                isWholeLine: true, 
                className: 'monaco-error-line',
                linesDecorationsClassName: 'monaco-error-margin' 
            }
        });
    }

    if (globalTraceData.length > 0 && currentStepIndex >= 0 && isVisualizerVisible) {
        const step = globalTraceData[currentStepIndex];
        const current_line_num = step ? step.line : 0;
        if (current_line_num && current_line_num > 0) {
            monacoEditor.revealLineInCenterIfOutsideViewport(current_line_num);
        }
        
        if (currentStepIndex > 0 && isPrevLineVisible) {
            const prevStep = globalTraceData[currentStepIndex - 1];
            const previous_line_num = prevStep ? prevStep.line : 0;
            
            if (previous_line_num && previous_line_num > 0 && previous_line_num !== current_line_num) {
                newDecorations.push({
                    range: new monaco.Range(previous_line_num, 1, previous_line_num, 1),
                    options: { 
                        isWholeLine: true, 
                        className: 'monaco-prev-line',
                        linesDecorationsClassName: 'monaco-prev-margin'
                    }
                });
            }
        }
    }

    if (!monacoEditor._customDecorations) {
        monacoEditor._customDecorations = monacoEditor.createDecorationsCollection();
    }
    monacoEditor._customDecorations.set(newDecorations);
}

function initializeDebugMenu(traceData) {
    let allUnique = new Set();
    visibleVariables.clear();

    traceData.forEach(step => {
        if (step.vars) {
            Object.keys(step.vars).forEach(varName => {
                if (!varName.startsWith('__')) allUnique.add(varName);
            });
        }
    });

    allUnique.forEach(v => visibleVariables.add(v));
    if (allUnique.size === 0) return;

    if(debugList) debugList.innerHTML = '';
    allUnique.forEach(varName => {
        const item = document.createElement('label');
        item.className = 'var-toggle-item';
        item.innerHTML = `<input type="checkbox" checked onchange="toggleVar('${varName}', this.checked)"> <span>${varName}</span>`;
        if(debugList) debugList.appendChild(item);
    });
}

function toggleVar(varName, isVisible) {
    isVisible ? visibleVariables.add(varName) : visibleVariables.delete(varName);
    if (globalTraceData.length > 0) renderMemory(globalTraceData[currentStepIndex]);
}

function printToConsole(text, type = "normal") {
    const span = document.createElement('span');
    span.textContent = text + '\n';
    if (type === "error") span.className = "text-err";
    if (type === "system") span.className = "text-sys";
    if(consoleOutput) {
        consoleOutput.appendChild(span);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }
}

function setupTrace(traceData, fullOutput) {
    globalTraceData = traceData || [];
    globalOutput = fullOutput || "";
    currentStepIndex = 0;
    
    let simulatedStack = [];
    globalTraceData.forEach(step => {
        let stepGlobals = {};
        let stepLocals = {};

        if (step.vars) {
            Object.entries(step.vars).forEach(([k, v]) => {
                if (k.startsWith('[Global] ')) stepGlobals[k] = v;
                else stepLocals[k] = v;
            });
        }

        if (simulatedStack.length === 0) {
            if (step.func_name) simulatedStack.push({ funcName: step.func_name, vars: stepLocals });
        } else {
            let topFrame = simulatedStack[simulatedStack.length - 1];
            if (topFrame.funcName === step.func_name) {
                topFrame.vars = stepLocals; 
            } else {
                let existingIndex = simulatedStack.findIndex(f => f.funcName === step.func_name);
                if (existingIndex !== -1) {
                    simulatedStack = simulatedStack.slice(0, existingIndex + 1); 
                    simulatedStack[simulatedStack.length - 1].vars = stepLocals;
                } else {
                    simulatedStack.push({ funcName: step.func_name, vars: stepLocals });
                }
            }
        }

        step.callStackSnapshot = JSON.parse(JSON.stringify(simulatedStack));
        step.globalsSnapshot = JSON.parse(JSON.stringify(stepGlobals));
    });

    if(runBtn) runBtn.disabled = false;
    initializeDebugMenu(globalTraceData);

    if (globalTraceData.length > 0) {
        if (timeSlider) {
            timeSlider.max = globalTraceData.length - 1;
            timeSlider.disabled = false;
        }

        if (!isVisualizerVisible) currentStepIndex = globalTraceData.length - 1;
        else currentStepIndex = 0;
        renderStep(currentStepIndex);
    } else {
        if (timeSlider) {
            timeSlider.max = 0;
            timeSlider.value = 0;
            timeSlider.disabled = true;
        }
        if (stepCounter) stepCounter.innerText = "0/0";
        
        updateArrowPosition();
        if(consoleOutput) consoleOutput.innerHTML = '';
        printToConsole(globalOutput);
    }
}

function renderStep(index) {
    const step = globalTraceData[index];
    const prevStep = index > 0 ? globalTraceData[index - 1] : null; 
    
    if (!step) return;

    if (timeSlider) timeSlider.value = index;
    if (stepCounter) stepCounter.innerText = `${index + 1}/${globalTraceData.length}`;
    
    renderMemory(step, prevStep); 
    updateArrowPosition();

    if(prevBtn) prevBtn.disabled = index === 0;
    if(nextBtn) nextBtn.disabled = index === globalTraceData.length - 1;

    if(consoleOutput) consoleOutput.innerHTML = '';
    if (index === globalTraceData.length - 1) {
        printToConsole(globalOutput);
    } else {
        printToConsole("> Đang chạy từng bước...", "system");
    }
}

function renderMemory(step, prevStep) {
    if(!visualizerArea) return;
    visualizerArea.innerHTML = '';
    let hasData = false;

    let prevVarsMap = {};
    if (prevStep) {
        if (prevStep.globalsSnapshot) {
            Object.entries(prevStep.globalsSnapshot).forEach(([k, v]) => prevVarsMap['global_' + k] = JSON.stringify(v));
        }
        if (prevStep.callStackSnapshot) {
            prevStep.callStackSnapshot.forEach(frame => {
                Object.entries(frame.vars).forEach(([k, v]) => prevVarsMap[frame.funcName + '_' + k] = JSON.stringify(v));
            });
        }
    }

    const createFrameUI = (title, varsObj, isGlobal) => {
        const entries = Object.entries(varsObj || {}).filter(([k]) => !k.startsWith('__') && visibleVariables.has(k));
        
        const frameDiv = document.createElement('div');
        frameDiv.className = 'memory-frame';

        const header = document.createElement('div');
        header.className = 'frame-header' + (isGlobal ? ' global' : '');
        header.innerHTML = isGlobal ? `🌐 Biến Toàn Cục (Global)` : `📍 Frame: <span>${title}()</span>`;
        frameDiv.appendChild(header);

        if (entries.length === 0 && !isGlobal) {
            const emptyMsg = document.createElement('div');
            emptyMsg.style.cssText = 'color:#8b949e; font-size:13px; font-style:italic;';
            emptyMsg.textContent = 'Trống (Chưa có biến cục bộ)';
            frameDiv.appendChild(emptyMsg);
            visualizerArea.appendChild(frameDiv);
            hasData = true;
            return;
        } else if (entries.length === 0 && isGlobal) return;

        for (const [k, data] of entries) {
            const name = isGlobal ? k.replace('[Global] ', '') : k;
            const row = document.createElement('div');
            row.className = 'var-row';
            
            const mapKey = (isGlobal ? 'global_' : title + '_') + k;
            const currentValStr = JSON.stringify(data);
            
            if (!prevVarsMap.hasOwnProperty(mapKey)) {
                row.classList.add('var-new'); 
            } else if (prevVarsMap[mapKey] !== currentValStr) {
                row.classList.add('var-updated'); 
            }

            const nameDiv = document.createElement('div');
            nameDiv.className = 'var-name';
            nameDiv.textContent = name;
            
            const eqDiv = document.createElement('div');
            eqDiv.className = 'var-eq';
            eqDiv.textContent = '=';

            const valsDiv = document.createElement('div');
            valsDiv.className = 'var-values';

            let dataType = data.type || "prim";
            let dataVal = data.val !== undefined ? data.val : data;

            if (dataType === 'list') {
                const bOpen = document.createElement('span'); bOpen.className = 'var-symbol'; bOpen.textContent = '[';
                valsDiv.appendChild(bOpen);
                (Array.isArray(dataVal) ? dataVal : []).forEach(item => {
                    const block = document.createElement('div');
                    block.className = 'var-block';
                    block.textContent = item;
                    valsDiv.appendChild(block);
                });
                const bClose = document.createElement('span'); bClose.className = 'var-symbol'; bClose.textContent = ']';
                valsDiv.appendChild(bClose);
            } else if (dataType === 'object' || dataType === 'dict') {
                const objBox = document.createElement('div');
                objBox.className = 'var-obj-box';
                const header = document.createElement('div');
                header.className = 'var-obj-header';
                header.textContent = dataType === 'object' ? `Class: ${data.class_name}` : `Dictionary`;
                objBox.appendChild(header);

                const subEntries = Object.entries(dataVal || {});
                if (subEntries.length === 0) {
                    const empty = document.createElement('div');
                    empty.style.color = 'var(--text-muted)';
                    empty.style.fontSize = '12px';
                    empty.textContent = '{} (Trống)';
                    objBox.appendChild(empty);
                } else {
                    subEntries.forEach(([key, val]) => {
                        const objRow = document.createElement('div');
                        objRow.className = 'var-obj-row';
                        objRow.innerHTML = `<span class="var-obj-key">${key}:</span> <span class="var-obj-val">${val}</span>`;
                        objBox.appendChild(objRow);
                    });
                }
                valsDiv.appendChild(objBox);
            } else {
                const block = document.createElement('div');
                block.className = 'var-block';
                block.textContent = dataVal;
                valsDiv.appendChild(block);
            }

            row.appendChild(nameDiv);
            row.appendChild(eqDiv);
            row.appendChild(valsDiv);
            frameDiv.appendChild(row);
        }
        visualizerArea.appendChild(frameDiv);
        hasData = true;
    };

    if (step.globalsSnapshot) createFrameUI('', step.globalsSnapshot, true);
    if (step.callStackSnapshot && step.callStackSnapshot.length > 0) {
        step.callStackSnapshot.forEach(frame => createFrameUI(frame.funcName, frame.vars, false));
    }

    if (!hasData) visualizerArea.innerHTML = '<div style="color:#8b949e; font-size:13px; text-align:center; margin-top:40px;">Chưa có dữ liệu biến.</div>';
}

function nextStep() {
    if (currentStepIndex < globalTraceData.length - 1) {
        currentStepIndex++;
        renderStep(currentStepIndex);
    }
}

function prevStep() {
    if (currentStepIndex > 0) {
        currentStepIndex--;
        renderStep(currentStepIndex);
    }
}

// ==========================================
// 4. CHẠY CODE & FILE I/O
// ==========================================
async function runCode() {
    if (!monacoEditor) return;
    const code = monacoEditor.getValue();
    const lang = langSelect.value;
    const inputs = stdInput.value; 
    
    if(consoleOutput) consoleOutput.innerHTML = '';
    if(visualizerArea) visualizerArea.innerHTML = '';
    if(runBtn) runBtn.disabled = true;
    if(loader) loader.style.display = 'inline-block';
    currentErrorLine = -1;
    
    globalTraceData = [];
    updateArrowPosition();

    try {
        const fetchOptions = {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ language: lang, code: code, inputs: inputs }) 
        };

        const response = await fetch('/api/visualize/', fetchOptions);
        if (!response.ok) throw new Error(`Server trả về lỗi: ${response.status}`);
        const initResult = await response.json();
        
        if (initResult.error) {
            throw new Error(initResult.error);
        }

        let result = null;
        if (initResult.status === "SUCCESS") {
            result = initResult.result;
        } else {
            const taskId = initResult.task_id;
            printToConsole("Đang xếp hàng đợi Server xử lý...", "system");

            // Polling loop
            while (true) {
                await new Promise(r => setTimeout(r, 500)); // wait 500ms
                const statusRes = await fetch(`/api/task_status/${taskId}/`);
                if (!statusRes.ok) throw new Error(`Status lỗi: ${statusRes.status}`);
                
                const statusData = await statusRes.json();
                if (statusData.status === "SUCCESS") {
                    result = statusData.result;
                    break;
                } else if (statusData.status === "FAILURE") {
                    throw new Error(statusData.error || "Lỗi khi chạy code (Worker Failure)");
                }
                // If PENDING or running, continue loop
            }
        }

        if(consoleOutput) consoleOutput.innerHTML = '';

        if (result.time_ms !== undefined) {
            document.getElementById('timeMetric').innerText = result.time_ms.toFixed(2);
            document.getElementById('memMetric').innerText = result.memory_kb.toFixed(2);
        } else {
            document.getElementById('timeMetric').innerText = "0.00";
            document.getElementById('memMetric').innerText = "0.00";
        }

        if (result.error) {
            printToConsole("[" + lang.toUpperCase() + " Error] " + result.error, "error");
            if(runBtn) runBtn.disabled = false;

            if (result.error_line && result.error_line > 0) {
                currentErrorLine = result.error_line;
                updateArrowPosition();
            }
            return;
        }

        setupTrace(result.trace, result.output);
        
    } catch (err) {
        printToConsole("[Lỗi Kết Nối] " + err.message, "error");
        printToConsole("⚠️ Hãy đảm bảo Backend Server đang chạy tại http://localhost:8000/api/visualize", "system");
        if(runBtn) runBtn.disabled = false;
    } finally {
        if(loader) loader.style.display = 'none';
    }
}

// --- ĐỌC VÀ XỬ LÝ PHÍM TẮT ĐỘNG ---
function checkShortcut(e, shortcutStr) {
    if (!shortcutStr) return false;
    const parts = shortcutStr.split('+');
    const keyName = parts[parts.length - 1];
    const needsCtrl = parts.includes('Ctrl');
    const needsAlt = parts.includes('Alt');
    const needsShift = parts.includes('Shift');
    const needsMeta = parts.includes('Meta');

    const hasCtrl = e.ctrlKey;
    const hasAlt = e.altKey;
    const hasShift = e.shiftKey;
    const hasMeta = e.metaKey;

    let eKey = e.key;
    if (eKey === ' ') eKey = 'Space';
    if (eKey.length === 1) eKey = eKey.toUpperCase();

    if (eKey !== keyName) return false;
    if (needsCtrl !== hasCtrl) return false;
    if (needsAlt !== hasAlt) return false;
    if (needsShift !== hasShift) return false;
    if (needsMeta !== hasMeta) return false;

    return true;
}

document.addEventListener('keydown', function(e) {
    const scRunCode = localStorage.getItem('sc_runCode') || 'Ctrl+Enter';
    const scNextStep = localStorage.getItem('sc_nextStep') || 'Ctrl+ArrowRight';
    const scPrevStep = localStorage.getItem('sc_prevStep') || 'Ctrl+ArrowLeft';

    if (checkShortcut(e, scRunCode)) {
        e.preventDefault();
        if (runBtn && !runBtn.disabled) runCode();
    } else if (checkShortcut(e, scNextStep)) {
        e.preventDefault();
        if (nextBtn && !nextBtn.disabled) nextStep();
    } else if (checkShortcut(e, scPrevStep)) {
        e.preventDefault();
        if (prevBtn && !prevBtn.disabled) prevStep();
    }
});

const fileInput = document.getElementById('fileInput');
if(fileInput) {
    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = function(e) {
            if (monacoEditor) monacoEditor.setValue(e.target.result);
            
            const fileName = file.name.toLowerCase();
            if (fileName.endsWith('.cpp') || fileName.endsWith('.c') || fileName.endsWith('.h')) {
                if(langSelect) langSelect.value = 'cpp';
                changeLanguage();
            } else if (fileName.endsWith('.py')) {
                if(langSelect) langSelect.value = 'python';
                changeLanguage();
            }
        };
        reader.readAsText(file);
        this.value = '';
    });
}

function saveCodeLocal() {
    if (!monacoEditor) return;
    const code = monacoEditor.getValue();
    const lang = langSelect ? langSelect.value : 'python';
    const ext = lang === 'cpp' ? 'cpp' : 'py';
    const filename = `my_code.${ext}`;
    
    const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    const url = URL.createObjectURL(blob);
    a.href = url;
    a.download = filename;
    
    document.body.appendChild(a);
    a.click();
    
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

async function saveSnippet() {
    if (!monacoEditor) return;
    const code = monacoEditor.getValue();
    const lang = langSelect ? langSelect.value : 'python';
    const inputs = stdInput ? stdInput.value : '';
    
    if(loader) loader.style.display = 'inline-block';
    
    try {
        const payload = {
            language: lang,
            code: code,
            inputs: inputs
        };
        
        if (window.currentSnippetHash) {
            payload.hash_id = window.currentSnippetHash;
        }
        
        const response = await fetch('/api/save_snippet/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const result = await response.json();
        
        if (result.success) {
            window.location.href = '/s/' + result.hash_id + '/';
        } else {
            alert('Lỗi khi lưu code: ' + result.error);
        }
    } catch (err) {
        alert('Lỗi kết nối: ' + err.message);
    } finally {
        if(loader) loader.style.display = 'none';
    }
}

// Chú ý: Phần Anti-Cheat đã được di chuyển sang common.js để áp dụng cho mọi trang!

if (timeSlider) {
    timeSlider.addEventListener('input', function() {
        const newIndex = parseInt(this.value);
        currentStepIndex = newIndex;
        renderStep(newIndex); // Tự động render lại UI khi kéo
    });
}