/**
 * Глобальные утилиты для веб-клиента.
 */

/**
 * Экранирование HTML-символов для предотвращения XSS.
 * @param {string} str - Необработанная строка.
 * @returns {string} - Экранированная строка.
 */
function escapeHTML(str) {
    if (!str) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(str).replace(/[&<>"']/g, function(m) { return map[m]; });
}

// Экспорт для использования в модулях (опционально)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { escapeHTML };
}
