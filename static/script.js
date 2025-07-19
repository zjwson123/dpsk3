// 全局变量
let defectDistributionChart = null;
let highFrequencyChart = null;
// 全局变量
let currentProjectId = null;
let currentInspectionId = null;
let defectRecords = [];
let currentImageIndex = 0;
let imageRotationInterval = null;


// jQuery 初始化
$(document).ready(function() {
    // 初始化项目列表
    initProjectList();

    // 默认加载第一个项目
    const $firstProject = $('.project-item').first();
    if ($firstProject.length) {
        $firstProject.click();
    }

    // 侧边栏切换逻辑
    $('#toggleSidebar').click(function() {
        $('#project-sidebar').toggleClass('collapsed');
        $('#main-content').toggleClass('expanded');

        const icon = $(this).find('i');
        if ($('#project-sidebar').hasClass('collapsed')) {
            icon.removeClass('fa-chevron-left').addClass('fa-chevron-right');
        } else {
            icon.removeClass('fa-chevron-right').addClass('fa-chevron-left');
        }

        // 调整图表大小
        resizeCharts();
    });
});

// 初始化项目列表
function initProjectList() {
    $('.project-item').off('click').on('click', function() {
        $('.project-item').removeClass('active');
        $(this).addClass('active');
        currentProjectId = $(this).data('project-id');
        console.log('当前项目ID:', currentProjectId);
        loadProjectData(currentProjectId);
    });
}

// 加载项目数据
function loadProjectData(projectId) {
    // 显示加载状态
    $('.info-value').text('-');

    // 获取项目基本信息
    fetch(`/api/project/${projectId}`)
        .then(response => {
            if (!response.ok) throw new Error('网络响应不正常');
            return response.json();
        })
        .then(data => {
            if (data.success) {
                updateProjectInfo(data.data.project_info);
                updatainspectionInfo(data.data.inspections);
            } else {
                console.error('API返回错误:', data.message);
            }
        })
        .catch(error => {
            console.error('获取项目信息失败:', error);
        });

    // 初始化或更新图表
    initCharts(projectId);
}

// 更新项目基本信息
function updateProjectInfo(projectData) {
    $('#project_full_name').text(projectData.project_full_name || '-');
    $('#builder_name').text(projectData.builder_name || '-');
    $('#total_area').text(projectData.total_area || '-');
    $('#duration').text(projectData.duration || '-');

    const advanceRate = projectData.advance_rate || 0; // 默认0，避免NaN
    $('#advance_rate').text(advanceRate + '%');

    // 更新进度条宽度和颜色
    const progressBar = $('#progress_bar');
    progressBar.css('width', advanceRate + '%'); // 设置宽度
}

// 修改selectInspection函数，自动加载检测结果（如果已检测）
function selectInspection(element) {
    $('.inspection-item').removeClass('active');
    $(element).addClass('active');
    currentInspectionId = $(element).data('id');
    $('#detect-defect-btn').prop('disabled', false);

    // 检查是否已检测
    const hasDetection = $(element).find('.badge').hasClass('bg-success');

    if (hasDetection) {
        // 如果已检测，自动加载结果
        loadInspectionResults(currentInspectionId);
    } else {
        // 未检测则清空当前显示
        clearDefectDisplay();
    }
}

// 新增函数：清空病害显示
function clearDefectDisplay() {
    defectRecords = [];
    $('#defect-records-list').empty().append('<div class="text-center text-muted">暂无病害记录</div>');
    $('#defect-image').attr('src', 'https://images.unsplash.com/photo-1543857778-c4a1a569e7bd?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80');
    $('#current-image-index').text('0');
    $('#total-images-count').text('0');
    $('#defect-details').remove();

    // 重计统计信息
    $('#total-images-count').text('0');
    $('#defect-images-count').text('0');
    $('#total-defects-count').text('0');
}

async function loadInspectionResults(inspectionId) {
    try {

        //$('#defect-details-sidebar').addClass('d-none');
        //$('.defect-image-wrapper').closest('.col-md-8').removeClass('col-md-8').addClass('col-md-12');

        // 显示加载状态
        $('#defect-records-list').empty().append('<div class="text-center text-muted">正在加载检测结果...</div>');
        $('#defect-image').attr('src', 'https://via.placeholder.com/800x600?text=加载中...');

        const response = await fetch(`/api/inspection/${inspectionId}/results`);

        // 检查HTTP状态码
        if (!response.ok) {
            const errorText = await response.text();
            console.error(`HTTP错误! 状态码: ${response.status}, 响应: ${errorText}`);
            throw new Error(`请求失败，状态码: ${response.status}`);
        }

        //const response = await fetch(`/api/inspection/${inspectionId}/results`);
        const data = await response.json();

        console.log('API返回数据:', data);  // 调试用

        // 检查API返回结构
        if (!data || typeof data !== 'object') {
            console.error('无效的响应数据:', data);
            throw new Error('无效的响应数据格式');
        }

        // 检查success标志
        if (!data.success) {
            console.error('API返回失败:', data.message || '未知错误');
            throw new Error(data.message || 'API返回失败');
        }

        // 检查records是否存在
        if (!data.data || !data.data.records || !Array.isArray(data.data.records)) {
            console.error('无效的检测结果数据:', data.data);
            throw new Error('无效的检测结果数据格式');
        }

        // 更新数据
        //defectRecords = data.data.records;
        defectRecords = data.data.records.map(record => {
            // 可以在这里对路径进行额外处理
            return {
                ...record,
                // 确保路径是正确的格式
                image_path: record.image_path || record.image_name
            };
        });
        updateDefectStatistics(data.data);
        updateDefectRecordsList(defectRecords);

        // 如果有数据则开始轮播
        if (defectRecords.length > 0) {
            startImageRotation();
        } else {
            $('#defect-image').attr('src', 'https://via.placeholder.com/800x600?text=无病害图像');
        }

    } catch (error) {
        console.error('加载检测结果时出错:', error);
        $('#defect-records-list').empty().append(`<div class="text-center text-danger">加载失败: ${error.message}</div>`);
    }
}

// 更新病害统计信息 - 添加调试信息
function updateDefectStatistics(stats) {
    console.log('更新统计信息:', stats);

    // 使用新的ID更新统计信息
    $('#total-images-stat').text(stats.total_images || '0');  // 总图片数
    $('#defect-images-count').text(stats.defect_images || '0');  // 有病害的图片数
    $('#total-defects-count').text(stats.total_defects || '0');  // 总缺陷数

    // 更新图片计数器（显示有病害的图片数量）
    $('#image-total-count').text(stats.defect_images || '0');
    console.log('更新统计信息:', stats.defect_images);
}

// 更新发现记录列表（增强版）
function updateDefectRecordsList(records) {
    const $list = $('#defect-records-list');
    $list.empty();

    if (!records || records.length === 0) {
        $list.append('<div class="text-center text-muted">暂无病害记录</div>');
        return;
    }

    records.forEach((record, index) => {
    const $recordItem = $(`
        <div class="record-item p-3 border-bottom hover-highlight"
             onclick="showImageByIndex(${index})"
             style="cursor: pointer;">
            <div class="d-flex align-items-center">
                <!-- 图片名称（占30%宽度） -->
                <div class="flex-basis-25 text-truncate me-2" style="min-width: 130px;">
                    <span title="${record.image_name || '-'}">${record.image_name || '-'}</span>
                </div>

                <!-- 病害类型（占30%宽度） -->
                <div class="flex-basis-25 text-truncate me-2" style="min-width: 150px;">
                    <span class="badge bg-info" style="min-width: 80px;">
                        ${record.defect_type || '-'}
                    </span>
                </div>

                <!-- 病害位置（占20%宽度） -->
                <div class="flex-basis-25 text-truncate me-2" style="min-width: 120px;">
                    <span class="badge bg-warning text-dark" style="min-width: 80px;">
                        ${record.location || '-'}
                    </span>
                </div>

                <!-- 时间（占20%宽度） -->
                <div class="flex-basis-25 text-truncate" style="min-width: 120px;">
                   <span title="${record.time || '-'}">
                        ${record.time ? record.time : '-'}  <!-- 直接显示完整时间（含秒） -->
                   </span>
                </div>
            </div>
        </div>
    `);
    $list.append($recordItem);
});
}

function showImageByIndex(index) {
    if (index >= 0 && index < defectRecords.length) {
        currentImageIndex = index;
        showCurrentImage();

        // 滚动到当前图片记录
        const $container = $('#defect-records-list');
        const $items = $container.find('.record-item');
        if ($items.length > 0) {
            const $target = $items.eq(index);
            const containerTop = $container.offset().top;
            const targetTop = $target.offset().top;
            $container.scrollTop($container.scrollTop() + (targetTop - containerTop));
        }

        // 显示当前记录的详情
        showCurrentDefectDetails(defectRecords[index]);
    }
}

// 开始轮播图像
// 修改startImageRotation函数
function startImageRotation() {
    if (imageRotationInterval) clearInterval(imageRotationInterval);

    if (defectRecords.length === 0) {
        $('#defect-image').attr('src', 'https://images.unsplash.com/photo-1543857778-c4a1a569e7bd?ixlib=rb-4.0.3&auto=format&fit=crop&w=800&q=80');
        $('#defect-details-sidebar').addClass('d-none');
        $('.defect-image-wrapper').closest('.col-md-8').removeClass('col-md-8').addClass('col-md-12');
        return;
    }

    currentImageIndex = 0;
    showCurrentImage();
    showCurrentDefectDetails(defectRecords[0]); // 初始显示第一条记录的详情

    imageRotationInterval = setInterval(() => {
        currentImageIndex = (currentImageIndex + 1) % defectRecords.length;
        showCurrentImage();
        showCurrentDefectDetails(defectRecords[currentImageIndex]); // 轮播时更新详情
    }, 2000);
}

// 修改showCurrentImage函数
function showCurrentImage() {
    if (defectRecords.length === 0) return;

    const record = defectRecords[currentImageIndex];

    // 使用检测结果图片（带有标注框）
    let imagePath = `/api/image/${encodeURIComponent(record.result_image_name)}`;

    // 添加时间戳防止缓存
    const timestamp = new Date().getTime();
    $('#defect-image').attr('src', `${imagePath}?t=${timestamp}`)
        .on('error', function() {
            // 如果加载标注图片失败，尝试加载原始图片并添加标注
            loadImageWithAnnotations(record);
        });

    // 更新图片计数器（只显示有病害的图片数量）
    $('#current-image-index').text(currentImageIndex + 1);
    $('#image-total-count').text(defectRecords.length);

    // 显示当前图片的病害详情
    showCurrentDefectDetails(record);

    // 高亮对应的记录项
    $('.record-item').removeClass('active');
    $(`.record-item:eq(${currentImageIndex})`).addClass('active');
}

// 新增函数：如果标注图片加载失败，尝试加载原始图片并添加标注
function loadImageWithAnnotations(record) {
    const originalImagePath = `/api/image/${encodeURIComponent(record.image_name)}`;
    const timestamp = new Date().getTime();

    $('#defect-image').attr('src', `${originalImagePath}?t=${timestamp}`)
        .on('load', function() {
            // 图片加载成功后，尝试添加标注（如果数据可用）
            try {
                const canvas = document.createElement('canvas');
                const img = this;
                canvas.width = img.naturalWidth;
                canvas.height = img.naturalHeight;

                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);

                // 这里应该从record中获取标注数据
                // 由于record中只有当前缺陷的信息，我们需要获取该图片的所有缺陷
                // 这需要后端支持或前端缓存所有记录

                // 临时解决方案：只显示当前缺陷
                ctx.strokeStyle = '#00FF00';
                ctx.lineWidth = 2;
                ctx.font = '14px Arial';

                // 假设record中有标注数据（实际需要从后端获取完整的标注数据）
                if (record.annotations) {
                    record.annotations.forEach(anno => {
                        ctx.strokeRect(anno.x1, anno.y1, anno.x2 - anno.x1, anno.y2 - anno.y1);
                        ctx.fillStyle = '#00FF00';
                        ctx.fillText(anno.label, anno.x1, anno.y1 - 5);
                    });
                }

                // 将canvas转换为图片显示
                const annotatedImage = new Image();
                annotatedImage.src = canvas.toDataURL('image/jpeg');
                $(img).replaceWith(annotatedImage);
            } catch (e) {
                console.error('添加标注时出错:', e);
            }
        })
        .on('error', function() {
            $(this).attr('src', 'https://via.placeholder.com/800x600?text=图片加载失败');
        });
}

// 新增函数：显示当前图片的病害详情
// 修改showCurrentDefectDetails函数
function showCurrentDefectDetails(record) {
    if (!record || Object.keys(record).length === 0) {
        $('#defect-details-sidebar').addClass('d-none');
        $('.defect-image-wrapper').closest('.col-md-8').removeClass('col-md-8').addClass('col-md-12');
        return;
    }

    // 显示右侧面板
    $('#defect-details-sidebar').removeClass('d-none');
    $('.defect-image-wrapper').closest('.col-md-12').removeClass('col-md-12').addClass('col-md-8');

    // 生成详情内容 - 分组显示
    const detailsHTML = `
        <div class="detail-group">
            <div class="detail-group-title"><i class="fas fa-clock"></i> 检测时间</div>
            <div class="detail-item">
                <div class="detail-value">${record.time || '-'}</div>
            </div>
        </div>

        <div class="detail-group">
            <div class="detail-group-title"><i class="fas fa-map-marker-alt"></i> 病害类型</div>
            <div class="detail-item">
                <div class="detail-value">${record.defect_type || '-'}</div>
            </div>
        </div>

        <div class="detail-group">
            <div class="detail-group-title"><i class="fas fa-file-image"></i> 图像信息</div>
            <div class="detail-item">
                <div class="detail-value">${record.image_name || '-'}</div>
            </div>
        </div>

        <div class="detail-group">
            <div class="detail-group-title"><i class="fas fa-bug"></i> 病害位置</div>
            <div class="detail-item">
                <div class="detail-value">${record.location || '-'}</div>
            </div>
        </div>
    `;

    // 更新详情内容
    $('#defect-details-sidebar .details-content').html(detailsHTML);
}

function startDefectDetection() {
    const $activeItem = $('.inspection-item.active');
    const inspectionId = $activeItem.data('id');

    if (!inspectionId) {
        alert('请先选择一条巡检记录');
        return;
    }

    $('#detect-defect-btn').prop('disabled', true).text('检测中...');
    $activeItem.find('.badge').removeClass('bg-warning bg-success')
               .addClass('bg-secondary').text('检测中...');

    fetch(`/api/start-detection/${inspectionId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            $activeItem.find('.badge').removeClass('bg-secondary')
                       .addClass('bg-success').text('已检测');
            alert('病害检测已完成！');

            // 重新加载检测结果
            loadInspectionResults(inspectionId);
        } else {
            $activeItem.find('.badge').removeClass('bg-secondary')
                       .addClass('bg-warning').text('检测失败');
            alert('检测失败: ' + (data.message || '未知错误'));
        }
    })
    .catch(error => {
        console.error('检测过程中出错:', error);
        $activeItem.find('.badge').removeClass('bg-secondary')
                   .addClass('bg-warning').text('检测失败');
        alert('检测过程中出错: ' + error.message);
    })
    .finally(() => {
        $('#detect-defect-btn').prop('disabled', false).text('病害检测');
    });
}

// 修改updatainspectionInfo函数，确保正确处理选中状态
function updatainspectionInfo(inspectionsData) {
    const $inspectionList = $('#inspection-list');
    $inspectionList.empty();

    $('#inspection_num').text(inspectionsData.length || '-');
    if (!inspectionsData || inspectionsData.length === 0) {
        $inspectionList.append(`
            <div class="text-center text-muted" style="padding: 20px;">暂无巡检记录</div>
        `);
        $('#detect-defect-btn').prop('disabled', true);
        return;
    }

    inspectionsData.forEach(inspection => {
        const inspectionTime = inspection.inspection_time || '-';
        const totalImages = inspection.total_images || '0';
        const formattedTime = inspectionTime.replace('_', '_');

        // 检查是否已有检测结果
        const hasDetection = inspection.has_detection || false;
        const detectionStatus = hasDetection ?
            '<span class="badge bg-success ml-2">已检测</span>' :
            '<span class="badge bg-warning ml-2">未检测</span>';

        const $listItem = $(`
            <a href="javascript:void(0);"
               class="list-group-item list-group-item-action inspection-item"
               data-id="${inspection.id || ''}"
               onclick="selectInspection(this)">
                <div class="d-flex w-100 justify-content-between">
                    <h5 class="mb-1">巡检时间: ${formattedTime} ${detectionStatus}</h5>
                    <small>图片数量: ${totalImages}</small>
                </div>
            </a>
        `);

        $inspectionList.append($listItem);
    });

    if (inspectionsData.length > 0) {
        const latestInspection = inspectionsData[0];
        $('#inspection_last_time').text(latestInspection.inspection_time || '-');
    }

    // 恢复选中状态（如果有）
    const selectedId = $inspectionList.data('selected-id');
    if (selectedId) {
        $inspectionList.find(`.inspection-item[data-id="${selectedId}"]`).addClass('active');
    }

    // 如果没有选中的项目，默认禁用按钮
    if (!selectedId) {
        $('#detect-defect-btn').prop('disabled', true);
    }
}
























// 更新项目统计信息
function updateProjectStats(statsData) {
    $('#inspection-area').text(statsData.inspection_area || '-');
    $('#inspection-time').text(statsData.inspection_time || '-');
    $('#total-photos').text(statsData.total_photos || '-');
    $('#defect-photos').text(statsData.defect_photos || '-');
}

// 初始化图表
function initCharts(projectId) {
    // 示例数据 - 实际应从API获取
    const mockDefectData = {
        labels: ['裂缝', '蜂窝', '露筋', '空洞', '其他'],
        datasets: [{
            data: [35, 25, 20, 15, 5],
            backgroundColor: [
                '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF'
            ]
        }]
    };

    const mockFrequencyData = {
        labels: ['B1区', 'B2区', 'C1区', 'C2区', 'D区'],
        datasets: [{
            label: '病害数量',
            data: [42, 35, 28, 15, 10],
            backgroundColor: 'rgba(54, 162, 235, 0.7)'
        }]
    };

    // 病害分布图表
    const defectCtx = $('#defect-distribution-chart');
    if (defectCtx.length) {
        if (defectDistributionChart) {
            defectDistributionChart.data = mockDefectData;
            defectDistributionChart.update();
        } else {
            defectDistributionChart = new Chart(defectCtx, {
                type: 'pie',
                data: mockDefectData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        }
    }

    // 高发区域图表
    const frequencyCtx = $('#high-frequency-chart');
    if (frequencyCtx.length) {
        if (highFrequencyChart) {
            highFrequencyChart.data = mockFrequencyData;
            highFrequencyChart.update();
        } else {
            highFrequencyChart = new Chart(frequencyCtx, {
                type: 'bar',
                data: mockFrequencyData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
    }
}

// 调整图表大小
function resizeCharts() {
    if (defectDistributionChart) defectDistributionChart.resize();
    if (highFrequencyChart) highFrequencyChart.resize();
}