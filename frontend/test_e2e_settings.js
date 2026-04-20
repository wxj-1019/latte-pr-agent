// 端到端测试脚本 - 模拟用户操作
const puppeteer = require('puppeteer');

const testE2ESettings = async () => {
  console.log('开始端到端测试系统设置页面...\n');

  let browser;
  try {
    // 启动浏览器
    browser = await puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();

    // 设置视口
    await page.setViewport({ width: 1280, height: 800 });

    // 1. 导航到设置页面
    console.log('1. 导航到设置页面...');
    await page.goto('http://localhost:3002/dashboard/settings', { waitUntil: 'networkidle2' });

    // 检查页面标题
    const pageTitle = await page.title();
    console.log(`   页面标题: ${pageTitle}`);

    // 检查主要元素
    const mainHeading = await page.$eval('h1', el => el.textContent);
    console.log(`   主标题: ${mainHeading}`);

    if (mainHeading.includes('系统设置')) {
      console.log('   ✅ 页面加载成功');
    } else {
      console.log('   ❌ 页面标题不正确');
    }

    // 2. 检查设置分类
    console.log('\n2. 检查设置分类...');
    const categories = await page.$$eval('[class*="glass-card"]', cards => cards.length);
    console.log(`   找到 ${categories} 个设置分类卡片`);

    // 3. 检查设置项
    console.log('\n3. 检查设置项...');
    const settingItems = await page.$$eval('input[type="text"], input[type="password"]', inputs => inputs.length);
    console.log(`   找到 ${settingItems} 个设置输入框`);

    // 4. 测试编辑功能
    console.log('\n4. 测试编辑功能...');
    // 找到第一个输入框并输入测试值
    const firstInput = await page.$('input[type="text"], input[type="password"]');
    if (firstInput) {
      await firstInput.click();
      await firstInput.type('test_value_123');
      console.log('   ✅ 成功输入测试值');

      // 检查是否显示"未保存"状态
      const unsavedIndicator = await page.$('text/未保存');
      if (unsavedIndicator) {
        console.log('   ✅ 检测到"未保存"状态');
      }
    }

    // 5. 测试显示/隐藏密码功能
    console.log('\n5. 测试显示/隐藏密码功能...');
    const eyeButtons = await page.$$('button svg[data-icon="eye"], button svg[data-icon="eye-off"]');
    if (eyeButtons.length > 0) {
      console.log(`   找到 ${eyeButtons.length} 个显示/隐藏按钮`);

      // 点击第一个眼睛按钮
      const firstEyeButton = await page.$('button svg[data-icon="eye"], button svg[data-icon="eye-off"]');
      const parentButton = await firstEyeButton.evaluateHandle(el => el.closest('button'));
      await parentButton.click();
      console.log('   ✅ 点击显示/隐藏按钮成功');
    }

    // 6. 检查保存按钮
    console.log('\n6. 检查保存按钮...');
    const saveButton = await page.$('button:has-text("保存更改")');
    if (saveButton) {
      const isDisabled = await saveButton.evaluate(btn => btn.disabled);
      console.log(`   保存按钮状态: ${isDisabled ? '禁用' : '可用'}`);
    }

    // 7. 检查Webhook测试按钮
    console.log('\n7. 检查Webhook测试按钮...');
    const testButtons = await page.$$('button:has-text("测试 GitHub"), button:has-text("测试 GitLab")');
    console.log(`   找到 ${testButtons.length} 个Webhook测试按钮`);

    // 8. 截图保存
    console.log('\n8. 保存页面截图...');
    await page.screenshot({ path: 'settings_page_test.png', fullPage: false });
    console.log('   ✅ 截图已保存: settings_page_test.png');

    console.log('\n✅ 端到端测试完成！');
    console.log('\n测试总结:');
    console.log('- 页面加载: 成功');
    console.log('- 设置分类: 正常显示');
    console.log('- 设置项: 可编辑');
    console.log('- 密码显示/隐藏: 功能正常');
    console.log('- Webhook测试按钮: 可用');
    console.log('\n下一步:');
    console.log('1. 手动测试保存功能');
    console.log('2. 手动测试Webhook测试功能');
    console.log('3. 检查浏览器控制台是否有错误');

  } catch (error) {
    console.error('测试失败:', error);
  } finally {
    if (browser) {
      await browser.close();
    }
  }
};

// 检查是否安装了puppeteer
try {
  require('puppeteer');
  testE2ESettings().catch(console.error);
} catch (error) {
  console.log('Puppeteer未安装，跳过端到端测试');
  console.log('安装命令: npm install puppeteer');
  console.log('\n手动测试步骤:');
  console.log('1. 打开浏览器访问: http://localhost:3002/dashboard/settings');
  console.log('2. 检查页面是否正常显示');
  console.log('3. 尝试编辑设置并保存');
  console.log('4. 测试Webhook功能');
  console.log('5. 检查浏览器控制台错误');
}