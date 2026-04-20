// 简单的前端测试脚本
const testFrontendSettings = async () => {
  console.log('测试前端设置页面...\n');

  // 1. 测试页面加载
  console.log('1. 测试设置页面加载...');
  try {
    const response = await fetch('http://localhost:3002/dashboard/settings');
    console.log(`   状态码: ${response.status}`);
    if (response.status === 200) {
      console.log('   成功: 页面加载成功');
    } else {
      console.log(`   失败: HTTP ${response.status}`);
    }
  } catch (error) {
    console.log(`   异常: ${error.message}`);
  }

  // 2. 测试API调用
  console.log('\n2. 测试设置API调用...');
  try {
    const response = await fetch('http://localhost:8000/settings', {
      headers: {
        'X-API-Key': 'j7Pl_ct9i8iskh2nFg4PwQQkJXxPCJpjWDOL35KDZFY=',
        'Content-Type': 'application/json'
      }
    });
    console.log(`   状态码: ${response.status}`);
    if (response.status === 200) {
      const data = await response.json();
      console.log('   成功: API调用成功');
      console.log(`   返回分类: ${Object.keys(data.categories).join(', ')}`);
    } else {
      console.log(`   失败: ${response.status} ${response.statusText}`);
    }
  } catch (error) {
    console.log(`   异常: ${error.message}`);
  }

  // 3. 测试Webhook API
  console.log('\n3. 测试Webhook API...');
  try {
    const response = await fetch('http://localhost:8000/settings/test-webhook', {
      method: 'POST',
      headers: {
        'X-API-Key': 'j7Pl_ct9i8iskh2nFg4PwQQkJXxPCJpjWDOL35KDZFY=',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ platform: 'github' })
    });
    console.log(`   状态码: ${response.status}`);
    if (response.status === 200) {
      const data = await response.json();
      console.log('   成功: Webhook测试API调用成功');
      console.log(`   测试结果: ${data.passed ? '通过' : '未通过'}`);
    } else {
      console.log(`   失败: ${response.status} ${response.statusText}`);
    }
  } catch (error) {
    console.log(`   异常: ${error.message}`);
  }

  console.log('\n测试完成!');
  console.log('\n手动测试步骤:');
  console.log('1. 打开浏览器访问: http://localhost:3002/dashboard/settings');
  console.log('2. 检查设置页面是否正常加载');
  console.log('3. 尝试编辑一个设置项并保存');
  console.log('4. 点击"测试 GitHub"按钮测试Webhook');
  console.log('5. 检查所有功能是否正常工作');
};

// 运行测试
testFrontendSettings().catch(console.error);