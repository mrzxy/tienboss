// 全局变量
let isMonitoring = false;
let monitoringInterval = null;

// 自定义日志函数
function tLog(...args) {
    const now = new Date();
    const timeString = now.toLocaleTimeString('zh-CN', { 
        hour12: false,
        hour: '2-digit',
        minute: '2-digit', 
        second: '2-digit',
        fractionalSecondDigits: 3
    });
    console.log(`tt3-[${timeString}]:`, ...args);
}

// 自定义错误日志函数
function tError(...args) {
    const now = new Date();
    const timeString = now.toLocaleTimeString('zh-CN', { 
        hour12: false,
        hour: '2-digit',
        minute: '2-digit', 
        second: '2-digit',
        fractionalSecondDigits: 3
    });
    console.error(`tt3-[${timeString}]:`, ...args);
}

// Discord webhook URL
let DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/1387993663837310996/Kuov6iYyG8nRaHzHjCaZcVbxlRvNQ82WwoXncU9i_e9sfQxuosgAgX919R22mDNMQQqO';
// DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/1388056531026841620/9xVZst5BI3tTNfhTBpGrrPm8EyeYgeAI2ZQuE8yrd-OHnbJmTgHLSAhI0yDoX3O35RnO';

/**
 * 解析HTML表格行，提取期权数据
 * @param {HTMLElement} row - 表格行元素 (<tr>)
 * @returns {Array} 期权数据数组，格式为 [{"text": "值", "color": "颜色"}]
 */
function parseOptionsRowToData(row) {
    const data = [];
    
    try {
        // 获取所有的td元素
        const cells = row.querySelectorAll('td');
        
        cells.forEach((cell, index) => {
            // 获取单元格的文本内容
            let text = cell.innerText?.trim() || '';
            
            // 清理文本：移除多余的空白字符和换行
            text = text.replace(/\s+/g, ' ').trim();
            
            // 获取颜色样式
            let color = '#FFFFFF'; // 默认白色
            
            // 从style属性中获取颜色
            const styleColor = cell.style.color;
            if (styleColor && styleColor !== 'transparent' && styleColor !== '') {
                color = styleColor;
            }
            
            // 从CSS类或计算样式中获取颜色（如果style中没有）
            if (color === '#FFFFFF' || color === 'white') {
                const computedStyle = window.getComputedStyle(cell);
                const computedColor = computedStyle.color;
                if (computedColor && computedColor !== 'rgb(255, 255, 255)' && computedColor !== 'white') {
                    color = computedColor;
                }
            }
            
            // 标准化颜色格式
            color = normalizeColor(color);
            
            // 只添加有文本内容的单元格
            if (text && text.length > 0) {
                data.push({
                    text: text,
                    color: color
                });
            }
        });
        
        tLog('解析的期权数据:', data);
        return data;
        
    } catch (error) {
        tError('解析期权行数据时出错:', error);
        return [];
    }
}

/**
 * 标准化颜色格式
 * @param {string} color - 原始颜色值
 * @returns {string} 标准化的颜色值
 */
function normalizeColor(color) {
    if (!color || color === 'transparent' || color === '') {
        return '#FFFFFF';
    }
    
    // 处理常见的颜色名称
    const colorMap = {
        'white': '#FFFFFF',
        'red': '#FF0000',
        'green': '#00FF00',
        'blue': '#0000FF',
        'yellow': '#FFFF00',
        'orange': '#FFA500',
        'purple': '#800080',
        'pink': '#FFC0CB',
        'cyan': '#00FFFF',
        'magenta': '#FF00FF',
        'lime': '#00FF00',
        'gold': '#FFD700'
    };
    
    // 转换为小写进行匹配
    const lowerColor = color.toLowerCase();
    if (colorMap[lowerColor]) {
        return colorMap[lowerColor];
    }
    
    // 处理rgb格式 rgb(255, 0, 0)
    const rgbMatch = color.match(/rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/i);
    if (rgbMatch) {
        const r = parseInt(rgbMatch[1]);
        const g = parseInt(rgbMatch[2]);
        const b = parseInt(rgbMatch[3]);
        
        // 转换为十六进制
        const hex = '#' + 
            r.toString(16).padStart(2, '0') + 
            g.toString(16).padStart(2, '0') + 
            b.toString(16).padStart(2, '0');
        return hex.toUpperCase();
    }
    
    // 处理rgba格式 rgba(255, 0, 0, 1)
    const rgbaMatch = color.match(/rgba\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*[\d.]+\s*\)/i);
    if (rgbaMatch) {
        const r = parseInt(rgbaMatch[1]);
        const g = parseInt(rgbaMatch[2]);
        const b = parseInt(rgbaMatch[3]);
        
        // 转换为十六进制
        const hex = '#' + 
            r.toString(16).padStart(2, '0') + 
            g.toString(16).padStart(2, '0') + 
            b.toString(16).padStart(2, '0');
        return hex.toUpperCase();
    }
    
    // 如果已经是十六进制格式，确保大写
    if (color.startsWith('#')) {
        return color.toUpperCase();
    }
    
    // 其他情况返回原值或默认白色
    return color || '#FFFFFF';
}



/**
 * 发送期权数据到MQTT
 * @param {Array} optionsData - 期权数据数组
 */
function sendOptionsDataToMQTT(optionsData) {
    try {
        const message = {
            data: optionsData,
            timestamp: Date.now(),
            source: 'blackbox_options_monitor'
        };
        
        tLog('准备发送MQTT消息:', message);
        
        // 使用已有的publishMsg函数发送到MQTT
        publishMsg('lis-msg/black_box', JSON.stringify(message));
        
    } catch (error) {
        tError('发送MQTT消息时出错:', error);
    }
}

// 美东时间转换和判断函数

// 更精确的美东时间处理函数（考虑夏令时和AM/PM）
function isWithin10MinutesEST(estTimeString) {
  try {
    const startTime = performance.now(); // 记录函数开始时间
    tLog(`检查时间: ${estTimeString}`);
    
    // 解析时间字符串
    let hours, minutes, seconds = 0;
    const timeMatch = estTimeString.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
    if (timeMatch) {
      hours = parseInt(timeMatch[1]);
      minutes = parseInt(timeMatch[2]);
      seconds = timeMatch[3] ? parseInt(timeMatch[3]) : 0;
    } else {
      tError('无法解析时间格式:', estTimeString);
      return false;
    }
    
    // 获取当前EST时间
    const now = new Date();
    const nowEST = new Date(now.toLocaleString("en-US", {timeZone: "America/New_York"}));
    
    // 获取EST当天的日期
    const estYear = nowEST.getFullYear();
    const estMonth = nowEST.getMonth();
    const estDate = nowEST.getDate();
    
    // 构造目标时间的两个可能版本（AM和PM）
    const targetAM = new Date(estYear, estMonth, estDate, hours, minutes, seconds);
    const targetPM = new Date(estYear, estMonth, estDate, hours + 12, minutes, seconds);
    
    // 计算时间差
    const diffAM = Math.abs(nowEST.getTime() - targetAM.getTime());
    const diffPM = Math.abs(nowEST.getTime() - targetPM.getTime());
    
    // 选择时间差更小的那个
    const minDiff = Math.min(diffAM, diffPM);
    const tenMinutesInMs = 10 * 60 * 1000;
    
    const isWithin10Min = minDiff <= tenMinutesInMs;
    
    const chosenTarget = diffAM < diffPM ? targetAM : targetPM;
    const chosenPeriod = diffAM < diffPM ? 'AM' : 'PM';
    
    const endTime = performance.now(); // 记录函数结束时间
    const executionTime = endTime - startTime;
    
    tLog(`当前EST时间: ${nowEST.toLocaleString()}`);
    tLog(`目标时间${chosenPeriod}: ${chosenTarget.toLocaleString()}`);
    tLog(`时间差: ${Math.round(minDiff/1000/60)}分钟, 是否在10分钟内: ${isWithin10Min}`);
    tLog(`函数执行时间: ${executionTime.toFixed(2)}ms`);
    
    return isWithin10Min;
  } catch (error) {
    tError('时间转换错误:', error);
    return false;
  }
}

// 测试时间判断函数
function testTimeFunction() {
  tLog('=== 测试时间判断函数 ===');
  
  const now = new Date();
  const nowEST = new Date(now.toLocaleString("en-US", {timeZone: "America/New_York"}));
  
  tLog(`当前本地时间: ${now.toLocaleString()}`);
  tLog(`当前EST时间: ${nowEST.toLocaleString()}`);
  
  // 测试用例
  const testCases = [
    nowEST.getHours() + ':' + String(nowEST.getMinutes()).padStart(2, '0'),  // 当前时间
    (nowEST.getHours()) + ':' + String(nowEST.getMinutes() + 5).padStart(2, '0'),  // 5分钟后
    (nowEST.getHours()) + ':' + String(nowEST.getMinutes() - 5).padStart(2, '0'),  // 5分钟前
    (nowEST.getHours()) + ':' + String(nowEST.getMinutes() + 15).padStart(2, '0'), // 15分钟后
    '10:16',  // 固定时间测试
    '22:16',  // 固定时间测试（24小时制）
  ];
  
  testCases.forEach(testTime => {
    tLog(`\n测试时间: ${testTime}`);
    const result = isWithin10MinutesEST(testTime);
    tLog(`结果: ${result}\n`);
  });
}

// 创建开始/暂停按钮
function createControlButton() {
  // 检查是否已存在按钮
  if (document.getElementById('blackbox-monitor-btn')) {
    return;
  }

  const button = document.createElement('button');
  button.id = 'blackbox-monitor-btn';
  button.textContent = '开始监听';
  button.title = '点击切换监听状态\nShift+点击测试时间函数';
  button.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    z-index: 10000;
    padding: 10px 20px;
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    font-size: 14px;
    font-weight: bold;
    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
  `;

  // button.addEventListener('click', toggleMonitoring);
  button.addEventListener('click', (e) => {
    // 如果按住Shift键，运行测试函数
    if (e.shiftKey) {
      testTimeFunction();
      return;
    }
    
    // 正常点击切换监听
    toggleMonitoring();
  });
  document.body.appendChild(button);
}


// 切换监听状态
function toggleMonitoring() {
  const button = document.getElementById('blackbox-monitor-btn');
  
  if (isMonitoring) {
    // 停止监听
    stopMonitoring();
    button.textContent = '开始监听';
    button.style.backgroundColor = '#4CAF50';
  } else {
    // 开始监听
    startMonitoring();
    button.textContent = '暂停监听';
    button.style.backgroundColor = '#f44336';
  }
}

// 开始监听
function startMonitoring() {
  if (isMonitoring) return;
  
  isMonitoring = true;
  tLog('开始监听 BlackBox Options...');
  
  // 防止浏览器进入后台模式
  document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
      tLog('⚠️ 页面进入后台，可能影响性能');
    } else {
      tLog('✅ 页面回到前台');
    }
  });
  
  // 保持页面活跃
  const keepAlive = setInterval(() => {
    if (isMonitoring) {
      // 发送一个不可见的请求来保持连接活跃
      fetch('data:text/plain,keepalive', { method: 'GET' }).catch(() => {});
    } else {
      clearInterval(keepAlive);
    }
  }, 30000); // 每30秒发送一次keepalive
  
  // 将当前列表的所有选项行标记为已处理
  const currentOptionRows = document.querySelectorAll('#optionStrip .k-master-row');
  currentOptionRows.forEach(row => {
    row.setAttribute('data-issend', '1');
  });
  tLog(`已标记 ${currentOptionRows.length} 个当前选项行为已处理`);
  
  // 启动while循环监听
  startWhileLoop();
}

// while循环监听函数
async function startWhileLoop() {
  tLog("isMonitoring", isMonitoring)
  let loopCount = 0;
  
  while (isMonitoring) {
    try {
      const loopStartTime = performance.now();
      loopCount++;
      
      tLog(`开始第${loopCount}次循环检查`);
      await processOptions();
      
      const loopEndTime = performance.now();
      const loopDuration = loopEndTime - loopStartTime;
      tLog(`第${loopCount}次循环完成，耗时: ${loopDuration.toFixed(2)}ms`);
      
      // 精确等待1秒
      const waitTime = Math.max(0, 1000 - loopDuration);
      if (waitTime > 0) {
        tLog(`等待${waitTime.toFixed(0)}ms后继续下一轮`);
        await new Promise(resolve => setTimeout(resolve, waitTime));
      }
    } catch (error) {
      tError('监听循环出错:', error);
      // 出错时也等待1秒再继续
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
}

// 停止监听
function stopMonitoring() {
  isMonitoring = false;
  tLog('停止监听 BlackBox Options');
}

// 处理选项数据
// 系统性能监控
let lastPerformanceCheck = 0;
let performanceCheckInterval = 30000; // 30秒检查一次

function checkSystemPerformance() {
  const now = Date.now();
  if (now - lastPerformanceCheck > performanceCheckInterval) {
    const memory = performance.memory;
    const timing = performance.timing;
    
    tLog(`系统性能检查 - 内存使用: ${Math.round(memory.usedJSHeapSize / 1024 / 1024)}MB / ${Math.round(memory.jsHeapSizeLimit / 1024 / 1024)}MB`);
    tLog(`页面加载时间: ${timing.loadEventEnd - timing.navigationStart}ms`);
    tLog(`DOM解析时间: ${timing.domContentLoadedEventEnd - timing.navigationStart}ms`);
    
    // 检查时间同步
    const localTime = new Date();
    const utcTime = new Date(localTime.toUTCString());
    const timeDiff = Math.abs(localTime.getTime() - utcTime.getTime());
    tLog(`时间同步检查 - 本地时间: ${localTime.toLocaleString()}, UTC时间: ${utcTime.toLocaleString()}, 时间差: ${timeDiff}ms`);
    
    lastPerformanceCheck = now;
  }
}

async function processOptions() {
  // 检查系统性能
  checkSystemPerformance();
  
  const optionRows = document.querySelectorAll('#optionStrip .k-master-row');
  
  // 倒序循环处理选项行
  for (let i = optionRows.length - 1; i >= 0; i--) {
    const row = optionRows[i];
    
    if (!isMonitoring) {
      return
    }
    // 检查是否已经处理过
    if (row.getAttribute('data-issend') === '1') {
      continue;
    }

    td_time = row.querySelector('td.time').innerText;
    if (!isWithin10MinutesEST(td_time)) {
      tLog(`not in 10 minutes ${td_time} ${Date.now()}`)
      // continue;
    }

    try {
      // 解析期权数据
      const optionsData = parseOptionsRowToData(row);
      tLog(optionsData)
      
      if (optionsData.length > 0) {
        // 发送解析后的数据到MQTT
        let pub_result = publishMsg('lis-msg/black_box', {
          "data": optionsData,
          "timestamp": Date.now(),
          "source": "blackbox_options_monitor"
        });
        tLog("pub_result", pub_result)
        await new Promise(resolve => setTimeout(resolve, 3000));
        
        tLog('已发送期权数据到MQTT:', optionsData);
        
        // 可选：仍然截图
        // await domToImg(row);
      }

      // 标记为已处理
      row.setAttribute('data-issend', '1');
      tLog('已处理选项行:', row);
      
    } catch (error) {
      tError('处理选项行时出错:', error);
    }
  }
}

// 发送图片到Discord
async function sendToDiscord(imageData, symbol = 'Unknown') {
  try {
    // 将base64图片数据转换为Blob
    const response = await fetch(imageData);
    const blob = await response.blob();
    
    // 创建FormData
    const formData = new FormData();
    formData.append('file', blob, `${symbol}_${Date.now()}.png`);
    
    // 添加消息内容
    const payload = {
      // content: `📊 **BlackBox Options Alert**\n\n**Symbol:** ${symbol}\n**Time:** ${new Date().toLocaleString('zh-CN')}\n**Source:** BlackBox Options Monitor`,
      // embeds: [{
      //   title: 'Options Data Captured',
      //   description: `Screenshot captured for ${symbol}`,
      //   color: 0x00ff00,
      //   timestamp: new Date().toISOString(),
      //   footer: {
      //     text: 'BlackBox Options Monitor'
      //   }
      // }]
    };
    
    formData.append('payload_json', JSON.stringify(payload));
    
    // 发送到Discord webhook
    const discordResponse = await fetch(DISCORD_WEBHOOK_URL, {
      method: 'POST',
      body: formData
    });
    
    if (discordResponse.ok) {
      tLog(`✅ 图片已成功发送到Discord: ${symbol}`);
      return true;
    } else {
      const errorText = await discordResponse.text();
      tError(`❌ 发送到Discord失败: ${discordResponse.status} - ${errorText}`);
      return false;
    }
    
  } catch (error) {
    tError('发送到Discord时出错:', error);
    return false;
  }
}

// 截图函数 - 你需要自己实现这个函数
async function domToImg(element) {
  return new Promise((resolve, reject) => {
    try {
      // 获取股票代码
      const symbol = element.getAttribute('data-symbol') || 'Unknown';
      
      // 使用 html2canvas 截图，提高分辨率
      html2canvas(element, {
        useCORS: true,
        allowTaint: true,
        backgroundColor: '#192026',
        scale: 8,                         // 增加放大倍数（原来是8，现在改为12）
        logging: false,                    // 关闭日志提升性能
        imageTimeout: 15000
      }).then(async canvas => {
       
        const imgData = canvas.toDataURL('image/png', 1.0); // 最高质量
        
        // 这里你可以处理图片数据
        // 比如保存到本地、上传到服务器等
        // console.log('截图完成:', imgDat);
        
        // 发送到Discord
        const success = await sendToDiscord(imgData, symbol);
        
        if (success) {
          tLog(`✅ ${symbol} 截图已发送到Discord`);
        } else {
          tError(`❌ ${symbol} 截图发送失败`);
        }
        
        resolve(imgData);
      }).catch(error => {
        tError('截图失败:', error);
        reject(error);
      });
    } catch (error) {
      console.error('domToImg 函数执行失败:', error);
      reject(error);
    }
  });
}

// 下载图片的辅助函数（可选）
function downloadImage(dataUrl, filename) {
  const link = document.createElement('a');
  link.download = filename;
  link.href = dataUrl;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// 注入自定义CSS样式
function injectCustomStyles() {
  // 检查是否已经注入过样式
  if (document.getElementById('blackbox-custom-styles')) {
    return;
  }

  const style = document.createElement('style');
  style.id = 'blackbox-custom-styles';
  style.textContent = `
    #optionStrip .k-grid-table {
      font-weight: bold !important;
      font-size: 14px !important;
    }
  `;
  
  document.head.appendChild(style);
  tLog('自定义CSS样式已注入');
}

// 页面加载完成后初始化
function init() {
  // 注入自定义样式
  injectCustomStyles();
  
  // 等待页面完全加载
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      createControlButton();
      injectCustomStyles(); // 确保样式已注入
    });
  } else {
    createControlButton();
    injectCustomStyles(); // 确保样式已注入
  }
  
  // 监听页面变化（如果页面是动态加载的）
  const observer = new MutationObserver(() => {
    if (!document.getElementById('blackbox-monitor-btn')) {
      createControlButton();
    }
  
    // 确保样式始终存在
    if (!document.getElementById('blackbox-custom-styles')) {
      injectCustomStyles();
    }
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
}

function getReactPropsName(domElement) {
  for (var key in domElement) {
    // 判断属性名是否以 "__reactProps" 开头，如果是则返回该属性名
    if (key.startsWith("__reactProps")) {
      return key;
    }
  }
  // 如果未找到对应的属性名，则返回 null
  return null;
}

function getRandomNum() {
  return Math.floor(Math.random() * 100000) + 1;
}
function connectMqtt() {
    const url = 'wss://f24a5dcf.ala.cn-hangzhou.emqxsl.cn:8084/mqtt'
    let role = "t3_listener"
    // Create an MQTT client instance
    const options = {
        // Clean session
        clean: true,
        connectTimeout: 4000,
        // Authentication
        clientId: role + '_' + getRandomNum(),
        username: 'dcaccount',
        password: 'f24a5dcf123',
                // 重连配置
                reconnectPeriod: 5000,  // 重连间隔5秒
                connectTimeout: 4000,   // 连接超时4秒
                keepalive: 60,         // 保活时间60秒
    }
    const client = mqtt.connect(url, options)
    client.on('connect', function () {
        tLog(`${client.username} connected!`)
    })


    return client
}

let client = connectMqtt()

function publishMsg(topic, content) {
    if (client.connected) {
        return client.publish(topic, JSON.stringify(content), {
            qos: 1,
        }, (err) => {
            if (err) {
                console.error(error)
            }
        })
    } else {
        tLog("mqtt not connected")
    }
    return false
}
// 启动插件
init(); 