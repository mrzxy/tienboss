# BlackBox Options Monitor Chrome 插件

这是一个 Chrome 插件 V3 项目，用于监听 BlackBox Stocks 的 Options 页面并自动截图。

## 功能特性

- 在指定页面右下角显示开始/暂停按钮
- 循环监听 `#optionStrip .k-master-row` 选择器
- 自动调用 `domToImg` 函数进行截图
- 为已处理的元素添加 `data-issend="1"` 标签
- 2秒循环间隔，避免重复处理
- 支持暂停和恢复监听

## 文件结构

```
blackbox/
├── manifest.json          # Chrome 插件配置文件
├── content.js             # 主要功能脚本
├── html2canvas.min.js     # 截图库
└── README.md              # 项目说明
```

## 安装方法

1. 打开 Chrome 浏览器
2. 进入 `chrome://extensions/`
3. 开启"开发者模式"
4. 点击"加载已解压的扩展程序"
5. 选择项目文件夹

## 使用方法

1. 访问 `https://members.blackboxstocks.com/options`
2. 页面右下角会出现"开始监听"按钮
3. 点击按钮开始监听
4. 再次点击可暂停监听

## 自定义配置

### 修改监听间隔
在 `content.js` 中修改 `setInterval` 的时间参数（默认2000ms）：

```javascript
monitoringInterval = setInterval(() => {
  if (isMonitoring) {
    processOptions();
  }
}, 2000); // 修改这里的数值
```

### 自定义截图函数
你可以修改 `domToImg` 函数来实现自己的截图逻辑：

```javascript
async function domToImg(element) {
  // 在这里实现你的截图逻辑
  // 可以使用 html2canvas 或其他方法
}
```

## 注意事项

- 插件只在 `https://members.blackboxstocks.com/options` 页面生效
- 需要确保 `html2canvas.min.js` 文件存在且可访问
- 建议在开发者工具中查看控制台输出以监控运行状态

## 技术栈

- Chrome Extension Manifest V3
- JavaScript ES6+
- html2canvas 截图库 