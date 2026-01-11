// 标注界面的JavaScript
let currentData = null;
let isModified = false;
let hasUnsavedChanges = false; // 新增：专门跟踪是否有未保存的更改

document.addEventListener('DOMContentLoaded', function () {
    // 检查URL参数
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.has('jump')) {
        const targetId = urlParams.get('jump');
        navigate(targetId);
    } else {
        loadCurrentSample();
    }

    // 监听output编辑器的修改
    const outputEditor = document.getElementById('output-editor');
    if (outputEditor) {
        outputEditor.addEventListener('input', function () {
            hasUnsavedChanges = true; // 标记为有未保存的更改
            // isModified = true; // 不再直接修改这个，因为它是服务端状态
            // updateModifiedStatus();
        });
    }

    // 自动更新进度（每30秒）
    setInterval(updateStatistics, 30000);
});

// 加载当前样本
function loadCurrentSample() {
    fetch('/api/current')
        .then(response => {
            // 允许404通过，因为它表示"无数据集加载"，而不是网络错误
            if (response.status === 404) {
                return response.json();
            }
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                if (data.error === 'No dataset loaded') {
                    showStatus('请先上传数据集', 'info');
                } else {
                    showStatus(data.error, 'error');
                }
                return;
            }

            currentData = data;
            isModified = data.is_modified || false;
            hasUnsavedChanges = false; // 加载新数据时重置未保存状态
            updateDisplay();
            updateStatistics();
        })
        .catch(error => {
            console.error('Error loading sample:', error);
            showStatus('加载数据失败，请检查网络连接', 'error');
        });
}

// 更新显示
function updateDisplay() {
    if (!currentData) return;

    // 更新基本信息
    document.getElementById('sample-id').textContent = currentData.id;
    document.getElementById('current-position').textContent =
        `${currentData.current_index + 1}/${currentData.total}`;

    // 更新质量标签
    const qualityBadge = document.getElementById('current-quality');
    if (qualityBadge) {
        qualityBadge.textContent = getQualityText(currentData.quality);
        qualityBadge.className = 'annotation-badge ' + currentData.quality;
    }

    // 更新状态
    updateModifiedStatus();

    // 更新已标注状态
    const annotatedStatus = document.getElementById('annotated-status');
    if (annotatedStatus) {
        annotatedStatus.textContent = currentData.is_annotated ? '是' : '否';
        annotatedStatus.style.color = currentData.is_annotated ? '#10b981' : '#6b7280';
    }

    // 更新对话历史
    updateHistoryDisplay();

    // 更新Input
    const inputContent = document.getElementById('input-content');
    if (inputContent) {
        inputContent.textContent = currentData.input || '（空）';
    }

    // 更新Output编辑器
    const outputEditor = document.getElementById('output-editor');
    if (outputEditor) {
        outputEditor.value = currentData.output || '';
    }
}

// 更新历史对话显示
function updateHistoryDisplay() {
    const historyContainer = document.getElementById('history-container');
    if (!historyContainer) return;

    historyContainer.innerHTML = '';

    if (currentData.history && Array.isArray(currentData.history)) {
        const turnCount = document.getElementById('turn-count');
        if (turnCount) {
            turnCount.textContent = currentData.history.length;
        }

        currentData.history.forEach((turn, index) => {
            const turnDiv = document.createElement('div');
            turnDiv.className = 'conversation-turn';

            const userContent = Array.isArray(turn) ? turn[0] : turn.user || '';
            const assistantContent = Array.isArray(turn) ? turn[1] : turn.assistant || '';

            turnDiv.innerHTML = `
                <div class="turn-header">
                    <i class="fas fa-user"></i> 用户 (轮次 ${index + 1})
                </div>
                <div class="turn-content">${escapeHtml(formatContent(userContent))}</div>
                <div class="turn-header">
                    <i class="fas fa-robot"></i> 助手 (轮次 ${index + 1})
                </div>
                <div class="turn-content">${escapeHtml(formatContent(assistantContent))}</div>
            `;

            historyContainer.appendChild(turnDiv);
        });
    } else {
        historyContainer.innerHTML = '<p style="text-align: center; color: #6b7280;">无对话历史</p>';
        const turnCount = document.getElementById('turn-count');
        if (turnCount) {
            turnCount.textContent = '0';
        }
    }
}

// 标注质量
function annotate(qualityType) {
    if (!currentData) {
        showStatus('请先加载数据集', 'error');
        return;
    }

    fetch('/api/annotate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            quality_type: qualityType
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const qualityNames = {
                    'excellent': '极优',
                    'good': '次优',
                    'poor': '劣质',
                    'discarded': '废弃'
                };
                showStatus(`标注为${qualityNames[qualityType]}成功`, 'success');

                // 如果是废弃，重置修改状态
                if (qualityType === 'discarded') {
                    isModified = false;
                    hasUnsavedChanges = false;
                }

                // 重新加载数据并自动跳转到下一个
                setTimeout(() => {
                    navigate('next');
                }, 300);
            } else {
                showStatus(data.error || '标注失败', 'error');
            }
        })
        .catch(error => {
            console.error('Error annotating:', error);
            showStatus('标注失败，请检查网络连接', 'error');
        });
}

// 保存输出修改
function saveOutput() {
    if (!currentData) {
        showStatus('请先加载数据集', 'error');
        return;
    }

    const outputEditor = document.getElementById('output-editor');
    if (!outputEditor) {
        showStatus('找不到输出编辑器', 'error');
        return;
    }

    const newOutput = outputEditor.value;
    if (!newOutput.trim()) {
        showStatus('输出内容不能为空', 'error');
        return;
    }

    fetch('/api/update_output', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            output: newOutput
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showStatus('输出保存成功', 'success');
                showStatus('输出保存成功', 'success');
                isModified = true; // 保存后变为已修改（服务端状态）
                hasUnsavedChanges = false; // 保存后重置未保存状态
                updateModifiedStatus();
                loadCurrentSample(); // 重新加载数据
            } else {
                showStatus(data.error || '保存失败', 'error');
            }
        })
        .catch(error => {
            console.error('Error saving output:', error);
            showStatus('保存失败，请检查网络连接', 'error');
        });
}

// 导航
function navigate(direction) {
    if (!currentData) return;

    // 检查是否有未保存的修改
    if (hasUnsavedChanges) {
        if (!confirm('当前样本有未保存的修改，确定要离开吗？')) {
            return;
        }
    }

    fetch('/api/navigate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ direction: direction })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                if (direction === 'next' && data.error === 'Navigation failed') {
                    showStatus('已经是最后一个样本了', 'info');
                } else if (direction === 'prev' && data.error === 'Navigation failed') {
                    showStatus('已经是第一个样本了', 'info');
                } else {
                    showStatus(data.error, 'error');
                }
                return;
            }

            currentData = data;
            currentData = data;
            isModified = data.is_modified || false;
            hasUnsavedChanges = false; // 导航后重置
            updateDisplay();
        })
        .catch(error => {
            console.error('Error navigating:', error);
            showStatus('导航失败，请检查网络连接', 'error');
        });
}

// 跳转到指定样本
function jumpToSample() {
    const jumpInput = document.getElementById('jump-to');
    const targetId = parseInt(jumpInput.value);

    if (isNaN(targetId) || targetId < 0) {
        showStatus('请输入有效的样本ID', 'error');
        return;
    }

    // 检查是否有未保存的修改
    if (hasUnsavedChanges) {
        if (!confirm('当前样本有未保存的修改，确定要跳转吗？')) {
            return;
        }
    }

    navigate(targetId.toString());
    jumpInput.value = '';
}

// 重置输出
function resetOutput() {
    if (!currentData) return;

    if (!confirm('确定要重置输出到原始状态吗？')) {
        return;
    }

    fetch('/api/reset_output', {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const outputEditor = document.getElementById('output-editor');
                if (outputEditor) {
                    outputEditor.value = data.output;
                }
                isModified = false;
                hasUnsavedChanges = false; // 重置
                updateModifiedStatus();
                showStatus('已重置为原始输出', 'success');
                loadCurrentSample(); // 重新加载数据
            } else {
                showStatus(data.error || '重置失败', 'error');
            }
        })
        .catch(error => {
            console.error('Error resetting:', error);
            showStatus('重置失败，请检查网络连接', 'error');
        });
}

// 导出标注结果
function exportAnnotations() {
    // 收集质量选项
    const qualities = [];
    document.querySelectorAll('input[name="export-quality"]:checked').forEach(cb => {
        qualities.push(cb.value);
    });

    if (qualities.length === 0) {
        showStatus('请至少选择一种质量类型', 'error');
        return;
    }

    // 收集状态选项
    const state = document.querySelector('input[name="export-state"]:checked').value;

    fetch('/api/export', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            export_mode: 'advanced',
            qualities: qualities,
            state: state
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showStatus('导出成功！开始下载...', 'success');

                // 自动下载文件
                setTimeout(() => {
                    window.location.href = `/api/download/${data.filename}`;
                }, 1000);
            } else {
                showStatus(data.error || '导出失败', 'error');
            }
        })
        .catch(error => {
            console.error('Error exporting:', error);
            showStatus('导出失败，请检查网络连接', 'error');
        });
}

// 更新统计信息
function updateStatistics() {
    fetch('/api/statistics')
        .then(response => response.json())
        .then(data => {
            if (data.error) return;

            // 更新总数和标注数
            if (document.getElementById('total-samples')) {
                document.getElementById('total-samples').textContent = data.total;
                document.getElementById('annotated-samples').textContent = data.annotated;
                document.getElementById('modified-samples').textContent = data.modified;

                // 更新进度条
                const progressPercent = data.progress.toFixed(1);
                document.getElementById('progress-percent').textContent = `${progressPercent}%`;
                const progressBar = document.getElementById('progress-bar');
                if (progressBar) {
                    progressBar.style.width = `${progressPercent}%`;
                }

                // 更新各类型数量
                document.getElementById('count-excellent').textContent = data.quality_counts.excellent;
                document.getElementById('count-good').textContent = data.quality_counts.good;
                document.getElementById('count-poor').textContent = data.quality_counts.poor;
                document.getElementById('count-discarded').textContent = data.quality_counts.discarded;
                document.getElementById('count-unannotated').textContent = data.quality_counts.unannotated;
                document.getElementById('count-annotated').textContent = data.annotated;
                document.getElementById('count-modified').textContent = data.modified;
            }
        })
        .catch(error => console.error('Error updating statistics:', error));
}

// 更新修改状态显示
function updateModifiedStatus() {
    const modifiedStatus = document.getElementById('modified-status');

    if (modifiedStatus) {
        modifiedStatus.textContent = isModified ? '是' : '否';
        modifiedStatus.style.color = isModified ? '#10b981' : '#6b7280';
    }
}

// 显示状态消息
function showStatus(message, type = 'info') {
    const statusDiv = document.getElementById('status-message');
    if (!statusDiv) {
        // 创建状态消息元素
        const newStatusDiv = document.createElement('div');
        newStatusDiv.id = 'status-message';
        newStatusDiv.className = `status-message ${type}`;
        newStatusDiv.textContent = message;
        document.body.appendChild(newStatusDiv);

        // 自动隐藏
        setTimeout(() => {
            newStatusDiv.className = 'status-message';
            setTimeout(() => {
                if (newStatusDiv.parentNode) {
                    newStatusDiv.parentNode.removeChild(newStatusDiv);
                }
            }, 300);
        }, 3000);
        return;
    }

    statusDiv.textContent = message;
    statusDiv.className = `status-message ${type}`;

    // 自动隐藏
    setTimeout(() => {
        statusDiv.className = 'status-message';
    }, 3000);
}

// 辅助函数
function getQualityText(type) {
    const map = {
        'unannotated': '未标注',
        'excellent': '极优',
        'good': '次优',
        'poor': '劣质',
        'discarded': '废弃'
    };
    return map[type] || type;
}

function formatContent(content) {
    if (!content) return '（空）';
    return content;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 键盘快捷键
document.addEventListener('keydown', function (e) {
    // 忽略在输入框中的按键
    if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') {
        return;
    }

    switch (e.key) {
        case 'ArrowLeft':
            e.preventDefault();
            navigate('prev');
            break;
        case 'ArrowRight':
            e.preventDefault();
            navigate('next');
            break;
        case '1':
            e.preventDefault();
            annotate('excellent');
            break;
        case '2':
            e.preventDefault();
            annotate('good');
            break;
        case '3':
            e.preventDefault();
            annotate('poor');
            break;
        case '4':
            e.preventDefault();
            annotate('discarded');
            break;
        case 's':
        case 'S':
            if (e.ctrlKey) {
                e.preventDefault();
                saveOutput();
            }
            break;
        case 'r':
        case 'R':
            if (e.ctrlKey) {
                e.preventDefault();
                resetOutput();
            }
            break;
    }
});

// 离开页面提示
window.addEventListener('beforeunload', function (e) {
    if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = '您有未保存的修改，确定要离开吗？';
    }
});