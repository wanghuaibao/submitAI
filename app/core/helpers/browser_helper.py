import time
import random
import asyncio
from typing import Optional, Dict, Any, List, Tuple
import logging

# 假设使用playwright进行自动化操作
try:
    from playwright.async_api import async_playwright, Browser, Page, BrowserContext, TimeoutError as PlaywrightTimeoutError
except ImportError:
    logging.warning("未安装playwright，某些功能可能无法使用")

logger = logging.getLogger(__name__)

class BrowserHelper:
    """浏览器操作助手类，提供强化的浏览器自动化功能"""
    
    def __init__(self, headless: bool = True, slow_mo: int = 50):
        self.headless = headless
        self.slow_mo = slow_mo
        self.browser = None
        self.context = None
        self.page = None
        self.max_retries = 3
        
        # 常用的用户代理字符串列表
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.3 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
        ]
    
    async def initialize(self) -> None:
        """初始化浏览器和上下文"""
        try:
            self.playwright = await async_playwright().start()
            
            # 使用更稳定的浏览器启动参数
            browser_args = [
                '--disable-dev-shm-usage',  # 解决内存共享问题
                '--no-sandbox',             # 在某些环境需要
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--disable-web-security',   # 避免跨域问题
                '--disable-features=IsolateOrigins,site-per-process',  # 避免iframe限制
                '--disable-site-isolation-trials',
                '--disable-breakpad',       # 禁用崩溃报告
                '--disable-features=TranslateUI',  # 禁用翻译提示
                '--ignore-certificate-errors',  # 忽略SSL证书错误
                '--disable-extensions',     # 禁用扩展
                '--disable-infobars'        # 禁用信息栏
            ]
            
            # 创建浏览器实例
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=browser_args
            )
            
            # 随机选择一个用户代理
            user_agent = random.choice(self.user_agents)
            
            # 创建浏览器上下文
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=user_agent,
                ignore_https_errors=True,
                # 绕过自动化检测
                bypass_csp=True,
                java_script_enabled=True
            )
            
            # 设置超时
            self.context.set_default_timeout(60000)  # 60秒
            
            # 创建新页面
            self.page = await self.context.new_page()
            
            # 添加错误处理
            self.page.on("pageerror", lambda err: logger.error(f"页面错误: {err}"))
            self.page.on("console", lambda msg: logger.info(f"控制台 {msg.type}: {msg.text}") if msg.type == "error" else None)
            
            logger.info("浏览器配置初始化")
            return True
        except Exception as e:
            logger.error(f"浏览器初始化失败: {str(e)}")
            await self.close()
            return False
    
    async def navigate(self, url: str, wait_until: str = "networkidle", timeout: int = 60000) -> bool:
        """增强的页面导航功能，带重试机制"""
        if not self.page:
            logger.error("页面对象未初始化")
            return False
            
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"导航尝试 {attempt}/{self.max_retries}: {url}")
                logger.info(f"正在导航到 {url}，等待条件: {wait_until}，超时时间: {timeout//1000}秒")
                
                # 导航到页面
                response = await self.page.goto(
                    url, 
                    wait_until=wait_until,
                    timeout=timeout
                )
                
                # 等待页面完全加载
                await self.page.wait_for_load_state("domcontentloaded")
                logger.info(f"成功导航到 {url}")
                
                # 等待页面完全加载
                logger.info("等待页面完全加载...")
                await asyncio.sleep(2)  # 额外等待时间
                
                # 检查Cookie同意弹窗
                await self.handle_cookie_consent()
                
                return True
                
            except PlaywrightTimeoutError:
                logger.error(f"导航到 {url} 超时")
                screenshot_path = f"logs/navigation_timeout_{int(time.time())}.png"
                try:
                    await self.page.screenshot(path=screenshot_path)
                    logger.info(f"已保存超时截图: {screenshot_path}")
                except Exception as ss_err:
                    logger.error(f"保存超时截图失败: {str(ss_err)}")
                
                if attempt < self.max_retries:
                    logger.info(f"将在 {attempt * 2} 秒后重试...")
                    await asyncio.sleep(attempt * 2)  # 指数退避
                    # 刷新浏览器上下文
                    await self.refresh_context()
                else:
                    logger.error(f"导航到 {url} 失败，达到最大重试次数")
                    return False
                    
            except Exception as e:
                logger.error(f"导航到 {url} 失败: {str(e)}")
                screenshot_path = f"logs/navigation_error_{int(time.time())}.png"
                try:
                    await self.page.screenshot(path=screenshot_path)
                    logger.info(f"已保存导航错误截图: {screenshot_path}")
                except Exception as ss_err:
                    logger.error(f"保存导航错误截图失败: {str(ss_err)}")
                
                if attempt < self.max_retries:
                    # 指数退避策略
                    wait_time = attempt * 2
                    logger.info(f"将在 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                    # 刷新浏览器上下文
                    await self.refresh_context()
                else:
                    logger.error(f"导航到 {url} 失败，达到最大重试次数")
                    return False
        
        return False
    
    async def refresh_context(self) -> None:
        """刷新浏览器上下文，以解决可能的状态问题"""
        try:
            # 关闭当前上下文和页面
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            
            # 随机选择一个新的用户代理
            user_agent = random.choice(self.user_agents)
            
            # 创建新的上下文
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=user_agent,
                ignore_https_errors=True,
                bypass_csp=True,
                java_script_enabled=True
            )
            
            # 设置超时
            self.context.set_default_timeout(60000)
            
            # 创建新页面
            self.page = await self.context.new_page()
            
            # 添加错误处理
            self.page.on("pageerror", lambda err: logger.error(f"页面错误: {err}"))
            self.page.on("console", lambda msg: logger.info(f"控制台 {msg.type}: {msg.text}") if msg.type == "error" else None)
            
            logger.info("浏览器上下文已刷新")
        except Exception as e:
            logger.error(f"刷新浏览器上下文失败: {str(e)}")
    
    async def handle_cookie_consent(self) -> None:
        """处理Cookie同意弹窗，根据实际情况可以扩展"""
        logger.info("检查是否存在Cookie同意弹窗...")
        
        # 常见的Cookie同意按钮选择器列表
        cookie_selectors = [
            "button:has-text('Accept')",
            "button:has-text('Accept All')",
            "button:has-text('接受')",
            "button:has-text('同意')",
            "button:has-text('我同意')",
            "button[id*='cookie'][id*='accept']",
            ".cookie-banner button",
            "#cookie-banner button",
            "[class*='cookie'] button",
            "[id*='cookie'] button",
            "[id*='consent'] button",
            "[class*='consent'] button",
            "button[class*='agree']"
        ]
        
        for selector in cookie_selectors:
            try:
                # 使用更安全的方式检查元素是否存在
                is_visible = await self.page.is_visible(selector, timeout=3000)
                if is_visible:
                    logger.info(f"发现Cookie同意弹窗: {selector}")
                    await self.page.click(selector)
                    logger.info("已点击Cookie同意按钮")
                    await asyncio.sleep(1)  # 等待弹窗消失
                    return
            except Exception:
                # 忽略检查过程中的错误
                pass
        
        logger.info("未发现Cookie同意弹窗")
    
    async def submit_form(self, form_selector: str, field_values: Dict[str, str], submit_button_selector: str = None) -> bool:
        """增强的表单提交功能"""
        try:
            if not self.page:
                logger.error("页面对象未初始化")
                return False
                
            # 确保表单可见
            logger.info(f"准备提交表单，选择器: {form_selector}")
            form_visible = await self.page.is_visible(form_selector, timeout=10000)
            if not form_visible:
                logger.error(f"表单选择器 {form_selector} 不可见")
                return False
            
            # 填写表单字段
            for field_selector, value in field_values.items():
                logger.info(f"填写字段: {field_selector}, 值: {value}...")
                
                # 确保字段可见并可交互
                try:
                    await self.page.wait_for_selector(field_selector, state="visible", timeout=10000)
                    
                    # 先清空字段
                    await self.page.fill(field_selector, "")
                    
                    # 随机化输入延迟，更像人类
                    await asyncio.sleep(random.uniform(0.1, 0.5))
                    
                    # 输入值
                    await self.page.fill(field_selector, value)
                    
                    # 随机化输入后延迟
                    await asyncio.sleep(random.uniform(0.3, 1.0))
                    
                except Exception as e:
                    logger.error(f"填写字段 {field_selector} 出错: {str(e)}")
                    return False
            
            logger.info("表单填写成功")
            
            # 检查是否存在验证码
            has_captcha = await self.check_captcha()
            if has_captcha:
                logger.error("检测到验证码，无法自动提交表单")
                # 保存截图
                await self.page.screenshot(path=f"logs/captcha_detected_{int(time.time())}.png")
                return False
            
            # 提交表单
            logger.info("准备提交表单...")
            
            if submit_button_selector:
                logger.info(f"找到提交按钮: {submit_button_selector}")
                
                # 等待按钮可用
                await self.page.wait_for_selector(submit_button_selector, state="visible", timeout=10000)
                
                # 点击提交按钮
                logger.info("点击提交按钮...")
                await self.page.click(submit_button_selector)
            else:
                # 尝试常见的提交按钮选择器
                submit_selectors = [
                    f"{form_selector} button[type='submit']",
                    f"{form_selector} input[type='submit']",
                    f"{form_selector} button:has-text('Submit')",
                    f"{form_selector} button:has-text('提交')",
                    f"{form_selector} button:has-text('发送')",
                    f"{form_selector} button:has-text('Send')",
                    f"{form_selector} .submit-button",
                    f"{form_selector} .btn-submit",
                    f"{form_selector} button.primary"
                ]
                
                submitted = False
                for selector in submit_selectors:
                    try:
                        is_visible = await self.page.is_visible(selector, timeout=3000)
                        if is_visible:
                            logger.info(f"找到提交按钮: {selector}")
                            await self.page.click(selector)
                            logger.info("点击提交按钮...")
                            submitted = True
                            break
                    except Exception:
                        pass
                
                if not submitted:
                    logger.error("未找到可点击的提交按钮")
                    return False
            
            # 等待提交完成，检查成功条件或错误提示
            # 注意：这里需要根据实际网站定制成功/失败的检测方式
            try:
                # 等待页面变化或导航完成
                logger.info("等待表单提交结果...")
                
                # 监测常见的提交成功指示
                success_selectors = [
                    "text='Thank you'", 
                    "text='提交成功'",
                    "text='已收到'",
                    "text='Success'",
                    ".success-message",
                    ".thank-you-page",
                    "[class*='success']"
                ]
                
                # 监测常见的错误消息
                error_selectors = [
                    ".error-message", 
                    "[class*='error']",
                    "text='failed'",
                    "text='错误'",
                    "text='Error'"
                ]
                
                # 先等待页面加载完成
                await asyncio.sleep(2)
                
                # 检查是否有成功消息
                for selector in success_selectors:
                    try:
                        success = await self.page.is_visible(selector, timeout=3000)
                        if success:
                            logger.info(f"检测到成功消息: {selector}")
                            # 保存成功截图
                            await self.page.screenshot(path=f"logs/submission_success_{int(time.time())}.png")
                            return True
                    except Exception:
                        pass
                
                # 检查是否有错误消息
                for selector in error_selectors:
                    try:
                        error = await self.page.is_visible(selector, timeout=3000)
                        if error:
                            error_text = await self.page.text_content(selector)
                            logger.error(f"表单提交错误: {error_text}")
                            # 保存错误截图
                            await self.page.screenshot(path=f"logs/submission_error_{int(time.time())}.png")
                            return False
                    except Exception:
                        pass
                
                # 如果没有明确的成功或错误指示，则认为提交可能成功
                logger.info("未检测到明确的成功或错误消息，假定提交已成功")
                await self.page.screenshot(path=f"logs/submission_result_{int(time.time())}.png")
                return True
                
            except PlaywrightTimeoutError:
                logger.error("提交表单超时")
                await self.page.screenshot(path=f"logs/submission_timeout_{int(time.time())}.png")
                return False
            
        except Exception as e:
            logger.error(f"提交表单失败: {str(e)}")
            # 保存错误截图
            try:
                await self.page.screenshot(path=f"logs/submission_exception_{int(time.time())}.png")
            except Exception:
                pass
            return False
    
    async def check_captcha(self) -> bool:
        """检查页面是否包含验证码"""
        logger.info("检查页面中是否存在验证码...")
        
        captcha_selectors = [
            "iframe[src*='captcha']",
            "iframe[src*='recaptcha']",
            "iframe[title*='captcha']",
            "iframe[title*='reCAPTCHA']",
            ".g-recaptcha",
            "#captcha",
            "[class*='captcha']",
            "[id*='captcha']",
            "img[src*='captcha']",
            "div[class*='recaptcha']"
        ]
        
        for selector in captcha_selectors:
            try:
                is_visible = await self.page.is_visible(selector, timeout=3000)
                if is_visible:
                    logger.error(f"检测到验证码: {selector}")
                    return True
            except Exception:
                pass
        
        logger.info("未检测到验证码")
        return False
    
    async def close(self) -> None:
        """关闭浏览器实例和资源"""
        try:
            if self.page:
                await self.page.close()
                self.page = None
            
            if self.context:
                await self.context.close()
                self.context = None
            
            if self.browser:
                await self.browser.close()
                self.browser = None
            
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
            
            logger.info("浏览器资源已释放")
        except Exception as e:
            logger.error(f"关闭浏览器资源时出错: {str(e)}")

# 使用示例
async def example_usage():
    browser_helper = BrowserHelper(headless=False, slow_mo=100)
    try:
        await browser_helper.initialize()
        success = await browser_helper.navigate("https://example.com")
        if success:
            # 提交表单示例
            form_data = {
                "#email": "example@example.com",
                "#name": "Test User"
            }
            await browser_helper.submit_form("form", form_data, "form button[type='submit']")
    finally:
        await browser_helper.close()

# 允许直接运行此模块进行测试
if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_usage()) 