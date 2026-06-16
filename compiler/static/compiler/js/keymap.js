const KEYMAP_TEMPLATES = {
    vscode: {
        runCode: "F5",
        suggestCode: "Ctrl+Space",
        formatCode: "Shift+Alt+F",
        commentLine: "Ctrl+/",
        uncommentLine: "Ctrl+/",
        indent: "Tab",
        unindent: "Shift+Tab",
        duplicateLine: "Shift+Alt+ArrowDown",
        moveLineUp: "Alt+ArrowUp",
        moveLineDown: "Alt+ArrowDown",
        deleteLine: "Ctrl+Shift+K",
        multiCursor: "Ctrl+D",
        openTemplate: "Ctrl+J",
        nextStep: "Ctrl+ArrowRight",
        prevStep: "Ctrl+ArrowLeft"
    },
    codeblocks: {
        runCode: "F9",
        suggestCode: "Ctrl+Space",
        formatCode: "Shift+Alt+F", 
        commentLine: "Ctrl+Shift+C",
        uncommentLine: "Ctrl+Shift+X",
        indent: "Tab",
        unindent: "Shift+Tab",
        duplicateLine: "Ctrl+D",
        moveLineUp: "Alt+ArrowUp", 
        moveLineDown: "Alt+ArrowDown", 
        deleteLine: "Ctrl+Shift+L",
        multiCursor: "Ctrl+R",
        openTemplate: "Ctrl+J",
        nextStep: "Ctrl+ArrowRight",
        prevStep: "Ctrl+ArrowLeft"
    }
};

const ACTION_LABELS = {
    runCode: "Chạy chương trình",
    suggestCode: "Gợi ý code",
    formatCode: "Căn chỉnh code (Format)",
    commentLine: "Comment code",
    uncommentLine: "Bỏ Comment code",
    indent: "Thụt lề (Indent)",
    unindent: "Xóa thụt lề (Unindent)",
    duplicateLine: "Nhân đôi dòng",
    moveLineUp: "Di chuyển dòng lên",
    moveLineDown: "Di chuyển dòng xuống",
    deleteLine: "Xóa dòng hiện tại",
    multiCursor: "Chọn nhiều từ giống nhau",
    openTemplate: "Gợi ý Template",
    nextStep: "Bước tiếp theo (Debug)",
    prevStep: "Bước trước đó (Debug)"
};

let defaultTemplate = Object.assign({}, KEYMAP_TEMPLATES.vscode);
let savedKeymap = JSON.parse(localStorage.getItem("uni_keymap"));
let currentKeymap = savedKeymap ? Object.assign(defaultTemplate, savedKeymap) : defaultTemplate;
let currentTemplateName = localStorage.getItem("uni_keymap_name") || "vscode";

// Đảm bảo cập nhật lại uni_keymap với các key mới thêm
if (savedKeymap) {
    localStorage.setItem("uni_keymap", JSON.stringify(currentKeymap));
}

// --- HÀM KIỂM TRA PHÍM TẮT DÙNG CHUNG ---
window.checkShortcut = function(e, shortcutStr) {
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
};

function renderKeymapEditor() {
    const list = document.getElementById("keymapEditorList");
    if (!list) return;
    
    const select = document.getElementById("keymapTemplateSelect");
    if (select) select.value = currentTemplateName;

    list.innerHTML = "";
    const isCustom = currentTemplateName === "custom";

    for (const [key, label] of Object.entries(ACTION_LABELS)) {
        const wrapper = document.createElement("div");
        wrapper.style.display = "flex";
        wrapper.style.justifyContent = "space-between";
        wrapper.style.alignItems = "center";
        wrapper.style.padding = "8px 12px";
        wrapper.style.background = "var(--bg-body)";
        wrapper.style.borderRadius = "8px";
        wrapper.style.border = "1px solid var(--border)";
        wrapper.style.boxShadow = "0 2px 4px rgba(0,0,0,0.02)";

        const labelEl = document.createElement("label");
        labelEl.innerText = ACTION_LABELS[key] || key;
        labelEl.style.fontSize = "13px";
        labelEl.style.color = "var(--text-main)";
        labelEl.style.fontWeight = "500";
        wrapper.appendChild(labelEl);

        const inputEl = document.createElement("input");
        inputEl.type = "text";
        inputEl.value = currentKeymap[key] || "";
        inputEl.readOnly = true;
        inputEl.style.width = "140px";
        inputEl.style.fontSize = "12px";
        inputEl.style.padding = "6px 12px";
        inputEl.style.borderRadius = "6px";
        inputEl.style.border = isCustom ? "1px solid var(--text-accent)" : "1px solid var(--border)";
        inputEl.style.background = isCustom ? "var(--bg-surface)" : "var(--bg-io)";
        inputEl.style.color = "var(--text-main)";
        inputEl.style.textAlign = "center";
        inputEl.style.cursor = isCustom ? "pointer" : "not-allowed";
        inputEl.style.boxShadow = isCustom ? "0 3px 0 var(--text-accent)" : "0 3px 0 var(--border)";
        inputEl.style.fontWeight = "bold";
        inputEl.style.fontFamily = "var(--font-code)";
        inputEl.style.transition = "all 0.2s ease";
        inputEl.style.transform = "translateY(-1px)";
        
        if (isCustom) {
            inputEl.addEventListener("mousedown", () => {
                inputEl.style.transform = "translateY(2px)";
                inputEl.style.boxShadow = "0 0 0 var(--text-accent)";
            });
            inputEl.addEventListener("mouseup", () => {
                inputEl.style.transform = "translateY(-1px)";
                inputEl.style.boxShadow = "0 3px 0 var(--text-accent)";
            });
            inputEl.addEventListener("mouseout", () => {
                inputEl.style.transform = "translateY(-1px)";
                inputEl.style.boxShadow = "0 3px 0 var(--text-accent)";
            });
        }

        if (isCustom) {
            inputEl.placeholder = "Bấm phím...";
            inputEl.addEventListener("keydown", (e) => {
                e.preventDefault();
                let keys = [];
                if (e.ctrlKey) keys.push("Ctrl");
                if (e.altKey) keys.push("Alt");
                if (e.shiftKey) keys.push("Shift");
                if (e.metaKey) keys.push("Meta");
                
                let keyName = e.key;
                if (keyName === " ") keyName = "Space";
                else if (keyName.length === 1) keyName = keyName.toUpperCase();
                
                if (!["Control", "Alt", "Shift", "Meta"].includes(keyName)) {
                    keys.push(keyName);
                }
                
                const combo = keys.join("+");
                inputEl.value = combo;
                currentKeymap[key] = combo;
                saveCurrentKeymap();
            });
        }

        wrapper.appendChild(inputEl);
        list.appendChild(wrapper);
    }
}

function changeKeymapTemplate() {
    const val = document.getElementById("keymapTemplateSelect").value;
    currentTemplateName = val;
    localStorage.setItem("uni_keymap_name", val);
    
    if (val !== "custom") {
        currentKeymap = Object.assign({}, KEYMAP_TEMPLATES[val]);
        saveCurrentKeymap();
    }
    renderKeymapEditor();
}

function saveCurrentKeymap() {
    localStorage.setItem("uni_keymap", JSON.stringify(currentKeymap));
    if (typeof applyMonacoKeymap === "function") {
        applyMonacoKeymap();
    }
}

async function saveKeymapToCloud(e) {
    const evt = e || event;
    const btn = evt ? evt.currentTarget : null;
    const originalText = btn ? btn.innerHTML : '';
    if (btn) btn.innerHTML = '<i class="ph-bold ph-spinner spinning"></i>';
    try {
        const res = await fetch("/api/keymap/save/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": window.csrfToken
            },
            body: window.encryptPayload({
                keymap_data: currentKeymap,
                name: "Custom Template"
            })
        });
        const data = await res.json();
        if (data.success) {
            const hashDisplay = document.getElementById("keymapHashDisplay");
            if (hashDisplay) hashDisplay.value = data.hash_id;
            if (btn) { btn.innerHTML = '<i class="ph-bold ph-check"></i> Đã lưu!'; setTimeout(() => { btn.innerHTML = originalText; }, 2000); return; }
        } else {
            alert("Lỗi: " + data.error);
        }
    } catch(e) {
        alert("Lỗi kết nối");
    } finally {
        if (btn && !btn.innerHTML.includes('check')) btn.innerHTML = originalText;
    }
}

async function loadKeymapFromCloud() {
    const hash = document.getElementById("keymapHashInput").value.trim();
    if (!hash) return;
    
    const btn = event.currentTarget;
    btn.innerHTML = '<i class="ph-bold ph-spinner spinning"></i>';
    try {
        const res = await fetch("/api/keymap/load/" + hash + "/");
        const data = await res.json();
        if (data.success) {
            currentKeymap = data.keymap_data;
            currentTemplateName = "custom";
            localStorage.setItem("uni_keymap_name", "custom");
            saveCurrentKeymap();
            document.getElementById("keymapTemplateSelect").value = "custom";
            renderKeymapEditor();
            alert("Đã tải Keymap thành công!");
        } else {
            alert("Lỗi: " + data.error);
        }
    } catch(e) {
        alert("Lỗi kết nối");
    } finally {
        btn.innerHTML = '<i class="ph-bold ph-cloud-arrow-down"></i> Tải về';
    }
}
