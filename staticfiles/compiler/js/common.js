// Cấu hình giao diện (Theme) trước khi render
if (localStorage.getItem('theme') === 'dark') {
    if (document.body) {
        document.body.classList.add('dark-theme');
    } else {
        document.documentElement.classList.add('dark-theme');
    }
}

// Logic điều khiển Dropdown menu người dùng
document.addEventListener('DOMContentLoaded', function() {
    window.addEventListener('click', function(event) {
        if (!event.target.closest('.user-dropdown')) {
            var dropdown = document.getElementById('userMenu');
            if (dropdown && dropdown.classList.contains('show')) {
                dropdown.classList.remove('show');
            }
        }
    });

    // Cập nhật text nút theme ban đầu
    const btn = document.getElementById('themeToggleBtn');
    if (btn && document.body.classList.contains('dark-theme')) {
        btn.innerText = '☀️';
    }

    applyEditorStyleToPanes();
});

function applyEditorStyleToPanes() {
    let themeName = localStorage.getItem('editor_theme');
    const isDark = document.body.classList.contains('dark-theme') || document.documentElement.classList.contains('dark-theme');
    
    if (!themeName || themeName.startsWith('unicorns-')) {
        themeName = isDark ? 'unicorns-dark' : 'unicorns-light';
    }

    const fontFamily = localStorage.getItem('editor_font_family') || "'Consolas', 'Fira Code', monospace";
    const fontSize = parseInt(localStorage.getItem('editor_font_size')) || 14;

    const root = document.documentElement;
    root.style.setProperty('--font-code', fontFamily);
    root.style.setProperty('--font-code-size', fontSize + 'px');

    const panes = [document.getElementById('ioWrapper'), document.getElementById('rightPane')];
    panes.forEach(pane => {
        if (!pane) return;
        
        if (themeName === 'vs-dark') {
            pane.style.setProperty('--bg-io', '#1e1e1e');
            pane.style.setProperty('--text-main', '#d4d4d4');
            pane.style.setProperty('--bg-panel', '#252526');
            pane.style.setProperty('--border', '#3e3e42');
            pane.style.setProperty('--var-name-color', '#9cdcfe');
            pane.style.setProperty('--block-bg', '#2d2d30');
            pane.style.setProperty('--block-text', '#cccccc');
        } else if (themeName === 'hc-black') {
            pane.style.setProperty('--bg-io', '#000000');
            pane.style.setProperty('--text-main', '#ffffff');
            pane.style.setProperty('--bg-panel', '#000000');
            pane.style.setProperty('--border', '#6fc3df');
            pane.style.setProperty('--var-name-color', '#9cdcfe');
            pane.style.setProperty('--block-bg', '#000000');
            pane.style.setProperty('--block-text', '#ffffff');
        } else if (themeName === 'vs') {
            pane.style.setProperty('--bg-io', '#ffffff');
            pane.style.setProperty('--text-main', '#000000');
            pane.style.setProperty('--bg-panel', '#f3f3f3');
            pane.style.setProperty('--border', '#e4e4e4');
            pane.style.setProperty('--var-name-color', '#0056b3');
            pane.style.setProperty('--block-bg', '#e9ecef');
            pane.style.setProperty('--block-text', '#212529');
        } else {
            // Revert to global
            pane.style.removeProperty('--bg-io');
            pane.style.removeProperty('--text-main');
            pane.style.removeProperty('--bg-panel');
            pane.style.removeProperty('--border');
            pane.style.removeProperty('--var-name-color');
            pane.style.removeProperty('--block-bg');
            pane.style.removeProperty('--block-text');
        }
    });
}

function switchThemeLogic() {
    document.body.classList.toggle('dark-theme');
    const btn = document.getElementById('themeToggleBtn');
    const isDark = document.body.classList.contains('dark-theme');
    
    const currentEditorTheme = localStorage.getItem('editor_theme');
    const syncEditor = !currentEditorTheme || currentEditorTheme.startsWith('unicorns-');

    if (isDark) {
        if(btn) btn.innerText = '☀️';
        localStorage.setItem('theme', 'dark');
        if (syncEditor && typeof monaco !== 'undefined' && typeof monacoEditor !== 'undefined' && monacoEditor) {
            monaco.editor.setTheme('unicorns-dark');
        }
    } else {
        if(btn) btn.innerText = '🌙';
        localStorage.setItem('theme', 'light');
        if (syncEditor && typeof monaco !== 'undefined' && typeof monacoEditor !== 'undefined' && monacoEditor) {
            monaco.editor.setTheme('unicorns-light');
        }
    }
    
    applyEditorStyleToPanes();
}

function toggleTheme(event) {
    const btn = document.getElementById('themeToggleBtn');
    if(btn) {
        btn.classList.add('theme-animate');
        setTimeout(() => btn.classList.remove('theme-animate'), 600);
    }

    if (!document.startViewTransition) {
        switchThemeLogic();
        return;
    }

    const x = event ? event.clientX : window.innerWidth / 2;
    const y = event ? event.clientY : window.innerHeight / 2;
    const endRadius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));

    const transition = document.startViewTransition(() => switchThemeLogic());

    transition.ready.then(() => {
        document.documentElement.animate(
            { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${endRadius}px at ${x}px ${y}px)`] },
            { duration: 500, easing: 'ease-in-out', pseudoElement: '::view-transition-new(root)' }
        );
    });
}

// ==========================================
// HỆ THỐNG PHÁT HIỆN GIÁN ĐIỆP (ANTI-CHEAT GLOBAL)
// ==========================================
function showSpyModal(e) {
    console.log("Anti-Cheat: showSpyModal called!", e ? e.type : "setInterval");
    if (window.isAdmin) return; // Trừ tài khoản admin
    if (e) e.preventDefault();
    const sm = document.getElementById('spyModal');
    console.log("Anti-Cheat: spyModal element found?", !!sm);
    if (sm) sm.style.display = 'block';
    return false;
}

function closeSpyModal() {
    const sm = document.getElementById('spyModal');
    if (sm) sm.style.display = 'none';
}

    // Chạy sau khi DOM tải xong
document.addEventListener('DOMContentLoaded', function() {
    // Hệ thống chặn phím tắt DevTools (bắt ở capture phase trên Window để ưu tiên tuyệt đối)
    if (!window.isAdmin) {
        window.addEventListener('keydown', function(e) {
            if (e.key === 'F12' || e.keyCode === 123) return showSpyModal(e);
            if (e.ctrlKey && e.shiftKey && ['I', 'J', 'C', 'i', 'j', 'c'].includes(e.key)) return showSpyModal(e);
            if (e.ctrlKey && (e.key === 'U' || e.key === 'u')) return showSpyModal(e);
            if (e.metaKey && ['u', 'i', 'j', 'c'].includes(e.key.toLowerCase())) return showSpyModal(e);
        }, true);
    }

    // --- CUSTOM CONTEXT MENU ---
    const contextMenu = document.getElementById('customContextMenu');
    
    // Ghi đè chuột phải trên toàn bộ trang
    document.addEventListener('contextmenu', function(e) {
        e.preventDefault(); // Chặn menu mặc định của trình duyệt
        
        if (!contextMenu) return;

        // Tính toán vị trí hiển thị để không bị tràn màn hình
        const menuWidth = 220; // Khớp với CSS
        const menuHeight = contextMenu.offsetHeight || 100; // Chiều cao xấp xỉ
        
        let x = e.pageX;
        let y = e.pageY;
        
        if (x + menuWidth > window.innerWidth) {
            x = window.innerWidth - menuWidth - 10;
        }
        if (y + menuHeight > window.innerHeight) {
            y = window.innerHeight - menuHeight - 10;
        }
        
        contextMenu.style.left = `${x}px`;
        contextMenu.style.top = `${y}px`;
        contextMenu.style.display = 'block';
    });

    // Ẩn menu khi click ra ngoài
    document.addEventListener('click', function(e) {
        if (contextMenu && contextMenu.style.display === 'block') {
            contextMenu.style.display = 'none';
        }
    });

    // Ẩn menu khi scroll
    document.addEventListener('scroll', function() {
        if (contextMenu && contextMenu.style.display === 'block') {
            contextMenu.style.display = 'none';
        }
    });
});

// Xử lý các hành động của Context Menu
function handleContextMenuAction(action, url = null) {
    const contextMenu = document.getElementById('customContextMenu');
    if (contextMenu) contextMenu.style.display = 'none';

    if (action === 'settings') {
        if (typeof toggleDebug === 'function') {
            toggleDebug();
        } else {
            alert('Trang này không có menu cài đặt.');
        }
    } else if (action === 'profile') {
        if (url) {
            window.location.href = url;
        }
    }
}
