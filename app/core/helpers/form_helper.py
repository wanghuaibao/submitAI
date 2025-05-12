import logging
import re
import time
import asyncio
from typing import Dict, List, Tuple, Optional, Any

# 假设使用playwright
try:
    from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
except ImportError:
    logging.warning("未安装playwright，某些功能可能无法使用")

logger = logging.getLogger(__name__)

class FormHelper:
    """提供高级表单分析和处理功能的助手类"""
    
    def __init__(self, page: Any):
        self.page = page
        self.timeout = 60000  # 默认60秒超时
        
        # 安全的CSS选择器，不使用:contains这种非标准选择器
        self.form_selectors = [
            "form", 
            ".form", 
            "#contact-form", 
            ".contact-form", 
            "[class*='submission-form']", 
            "div[role='form']",
            "[id*='form']"
        ]
        
        # 提交按钮的安全选择器
        self.submit_button_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button.submit",
            ".submit-button",
            "[type='submit']",
            "button.primary"
        ]
    
    async def find_form(self) -> Optional[str]:
        """查找页面中的表单，返回有效的表单选择器"""
        logger.info("开始查找表单选择器...")
        
        # 首先检查常见的表单选择器
        for selector in self.form_selectors:
            try:
                logger.info(f"尝试选择器: {selector}")
                # 检查表单是否存在且可见
                is_visible = await self.page.is_visible(selector, timeout=5000)
                if is_visible:
                    logger.info(f"找到可见的表单元素: {selector}")
                    
                    # 检查表单中的输入字段数量
                    field_count = await self.count_form_fields(selector)
                    logger.info(f"表单包含 {field_count} 个输入字段")
                    
                    # 如果表单中有输入字段，可能是有效的表单
                    if field_count > 0:
                        return selector
                else:
                    logger.info(f"找到表单但不可见: {selector}")
            except Exception as e:
                logger.info(f"选择器 {selector} 检查出错: {str(e)}")
        
        # 如果常见选择器都找不到，尝试查找包含表单的容器
        container_selectors = [
            "div[class*='form']",
            "div[id*='form']",
            "section[class*='form']",
            "div[class*='contact']",
            "section[class*='contact']"
        ]
        
        for container in container_selectors:
            try:
                container_visible = await self.page.is_visible(container, timeout=3000)
                if container_visible:
                    logger.info(f"在容器 {container} 中找到表单")
                    # 在容器中查找表单
                    for form in self.form_selectors:
                        form_selector = f"{container} {form}"
                        try:
                            form_visible = await self.page.is_visible(form_selector, timeout=3000)
                            if form_visible:
                                logger.info(f"找到表单选择器: {form_selector}")
                                return form_selector
                        except Exception:
                            pass
            except Exception:
                pass
        
        logger.error("未找到可见的表单元素")
        return None
    
    async def count_form_fields(self, form_selector: str) -> int:
        """计算表单中的输入字段数量"""
        try:
            input_count = await self.page.locator(f"{form_selector} input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='reset'])").count()
            textarea_count = await self.page.locator(f"{form_selector} textarea").count()
            select_count = await self.page.locator(f"{form_selector} select").count()
            
            return input_count + textarea_count + select_count
        except Exception as e:
            logger.error(f"计算表单字段数量时出错: {str(e)}")
            return 0
    
    async def get_form_fields(self, form_selector: str) -> List[Dict[str, str]]:
        """获取表单中所有可交互字段的信息"""
        logger.info("开始获取表单字段信息...")
        fields = []
        
        try:
            # 查找所有输入字段
            input_fields = await self.page.locator(f"{form_selector} input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='reset'])").all()
            
            for field in input_fields:
                try:
                    field_info = {}
                    field_info["type"] = await field.get_attribute("type") or "text"
                    field_info["name"] = await field.get_attribute("name") or ""
                    field_info["id"] = await field.get_attribute("id") or ""
                    field_info["placeholder"] = await field.get_attribute("placeholder") or ""
                    field_info["required"] = await field.get_attribute("required") is not None
                    field_info["selector"] = await self.get_best_selector(field)
                    
                    fields.append(field_info)
                except Exception as e:
                    logger.error(f"获取字段信息时出错: {str(e)}")
            
            # 查找文本区域
            textarea_fields = await self.page.locator(f"{form_selector} textarea").all()
            for field in textarea_fields:
                try:
                    field_info = {}
                    field_info["type"] = "textarea"
                    field_info["name"] = await field.get_attribute("name") or ""
                    field_info["id"] = await field.get_attribute("id") or ""
                    field_info["placeholder"] = await field.get_attribute("placeholder") or ""
                    field_info["required"] = await field.get_attribute("required") is not None
                    field_info["selector"] = await self.get_best_selector(field)
                    
                    fields.append(field_info)
                except Exception as e:
                    logger.error(f"获取文本区域信息时出错: {str(e)}")
            
            # 查找下拉菜单
            select_fields = await self.page.locator(f"{form_selector} select").all()
            for field in select_fields:
                try:
                    field_info = {}
                    field_info["type"] = "select"
                    field_info["name"] = await field.get_attribute("name") or ""
                    field_info["id"] = await field.get_attribute("id") or ""
                    field_info["required"] = await field.get_attribute("required") is not None
                    field_info["selector"] = await self.get_best_selector(field)
                    
                    # 获取选项
                    options = await self.page.locator(f"{field_info['selector']} option").all()
                    field_info["options"] = []
                    for option in options:
                        try:
                            option_value = await option.get_attribute("value") or ""
                            option_text = await option.inner_text()
                            field_info["options"].append({"value": option_value, "text": option_text})
                        except Exception:
                            pass
                    
                    fields.append(field_info)
                except Exception as e:
                    logger.error(f"获取下拉菜单信息时出错: {str(e)}")
            
            logger.info(f"表单字段信息已保存，找到 {len(fields)} 个字段")
            return fields
        except Exception as e:
            logger.error(f"获取表单字段时出错: {str(e)}")
            return []
    
    async def get_best_selector(self, element: Any) -> str:
        """为元素生成最佳CSS选择器"""
        # 首先尝试使用ID
        element_id = await element.get_attribute("id")
        if element_id:
            return f"#{element_id}"
        
        # 然后尝试使用name属性
        element_name = await element.get_attribute("name")
        if element_name:
            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
            return f"{tag_name}[name='{element_name}']"
        
        # 最后使用其他唯一属性或者组合属性
        element_class = await element.get_attribute("class")
        if element_class:
            classes = element_class.strip().split()
            if classes:
                tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                return f"{tag_name}.{classes[0]}"
        
        # 无法生成简单选择器时，返回一个相对路径
        return await element.evaluate("el => CSS.escape(el.tagName.toLowerCase())")
    
    async def find_submit_button(self, form_selector: str) -> Optional[str]:
        """查找表单的提交按钮"""
        logger.info("查找表单提交按钮...")
        
        for selector in self.submit_button_selectors:
            try:
                # 先尝试在表单内查找
                combined_selector = f"{form_selector} {selector}"
                is_visible = await self.page.is_visible(combined_selector, timeout=3000)
                if is_visible:
                    logger.info(f"找到提交按钮: {combined_selector}")
                    return combined_selector
            except Exception:
                pass
        
        # 如果在表单内找不到，尝试查找表单后面的按钮
        # 注意：这种方法不太可靠，但在某些特殊设计的表单中可能有用
        try:
            # 使用评估脚本查找表单后的按钮
            button = await self.page.evaluate("""(formSelector) => {
                const form = document.querySelector(formSelector);
                if (!form) return null;
                
                // 查找表单后的提交按钮
                let el = form.nextElementSibling;
                while (el) {
                    const button = el.querySelector('button, input[type="submit"], .submit-button, [type="submit"]');
                    if (button) return button.outerHTML;
                    el = el.nextElementSibling;
                }
                return null;
            }""", form_selector)
            
            if button:
                logger.info("找到表单外的提交按钮")
                
                # 从HTML中提取元素ID或类
                id_match = re.search(r'id=["\']([^"\']+)["\']', button)
                if id_match:
                    button_selector = f"#{id_match.group(1)}"
                    logger.info(f"使用ID选择器: {button_selector}")
                    return button_selector
                
                class_match = re.search(r'class=["\']([^"\']+)["\']', button)
                if class_match:
                    classes = class_match.group(1).split()
                    if classes:
                        button_selector = f".{classes[0]}"
                        logger.info(f"使用类选择器: {button_selector}")
                        return button_selector
        except Exception as e:
            logger.error(f"查找表单外按钮出错: {str(e)}")
        
        # 尝试使用Playwright的文本定位功能（使用正确的定位API）
        text_buttons = [
            "Submit", "Send", "提交", "发送", "确认", "订阅", "注册", "登录", "保存"
        ]
        
        for text in text_buttons:
            try:
                # 使用正确的文本定位方法
                button_selector = f"button:has-text(\"{text}\")"
                count = await self.page.locator(button_selector).count()
                if count > 0:
                    logger.info(f"使用文本找到按钮: {button_selector}")
                    return button_selector
            except Exception:
                # 忽略特定选择器的错误
                pass
        
        logger.error("未找到表单提交按钮")
        return None
    
    async def map_form_fields(self, user_data: Dict[str, str], form_fields: List[Dict[str, str]]) -> Dict[str, str]:
        """智能映射用户数据到表单字段"""
        logger.info(f"开始智能映射表单数据, 用户提供字段数: {len(user_data)}, 表单字段数: {len(form_fields)}")
        
        mapped_data = {}
        
        # 定义常见的字段类型和关键词
        field_types = {
            "name": ["name", "fullname", "full_name", "full-name", "姓名", "名字", "名称", "产品名", "product_name", "product-name", "tool_name", "tool-name"],
            "email": ["email", "mail", "e-mail", "邮箱", "电子邮件", "联系邮箱", "contact_email", "contact-email"],
            "url": ["url", "website", "web_site", "web-site", "site", "网址", "链接", "网站", "产品网址", "product_url", "product-url", "homepage", "home-page"],
            "description": ["description", "desc", "简介", "描述", "介绍", "产品描述", "product_description", "product-description", "about", "content"],
            "category": ["category", "类别", "分类", "产品类别", "product_category", "product-category", "type", "类型"],
            "price": ["price", "pricing", "价格", "费用", "价钱", "product_price", "product-price"],
            "features": ["features", "功能", "特点", "特性", "product_features", "product-features"],
            "logo": ["logo", "图标", "标志", "product_logo", "product-logo", "icon", "图片", "image"],
            "tags": ["tags", "标签", "关键词", "keywords", "product_tags", "product-tags"],
            "message": ["message", "留言", "信息", "备注", "消息", "content", "内容"]
        }
        
        # 对每个表单字段，尝试找到最匹配的用户数据
        for form_field in form_fields:
            field_name = form_field.get("name", "").lower()
            field_id = form_field.get("id", "").lower()
            field_placeholder = form_field.get("placeholder", "").lower()
            field_type = form_field.get("type", "").lower()
            field_selector = form_field.get("selector", "")
            
            # 根据字段属性猜测字段类型
            guessed_type = None
            
            # 按字段类型优先匹配
            if field_type == "email" or "email" in field_name or "email" in field_id or "email" in field_placeholder:
                guessed_type = "email"
            elif "url" in field_name or "url" in field_id or "website" in field_name or "website" in field_id or "链接" in field_placeholder:
                guessed_type = "url"
            elif "name" in field_name or "name" in field_id or "姓名" in field_placeholder:
                guessed_type = "name"
            elif "desc" in field_name or "desc" in field_id or "介绍" in field_placeholder or "description" in field_name:
                guessed_type = "description"
            elif "categ" in field_name or "categ" in field_id or "类别" in field_placeholder:
                guessed_type = "category"
            elif "price" in field_name or "price" in field_id or "价格" in field_placeholder:
                guessed_type = "price"
            elif "tag" in field_name or "tag" in field_id or "标签" in field_placeholder or "keyword" in field_name:
                guessed_type = "tags"
            elif field_type == "textarea":
                guessed_type = "description"
            
            # 对于每个表单字段，尝试在用户数据中找到最匹配的
            best_match = None
            for user_key, user_value in user_data.items():
                user_key_lower = user_key.lower()
                
                # 精确匹配
                if (field_name and field_name == user_key_lower) or (field_id and field_id == user_key_lower):
                    logger.info(f"精确匹配字段: {user_key} -> {field_selector}")
                    best_match = user_key
                    break
                
                # 部分匹配 (字段名称包含用户键或用户键包含字段名称)
                if not best_match and ((field_name and (field_name in user_key_lower or user_key_lower in field_name)) or 
                    (field_id and (field_id in user_key_lower or user_key_lower in field_id))):
                    logger.info(f"部分匹配字段: {user_key} -> {field_selector} (通过 name)")
                    best_match = user_key
                    continue
                
                # 类型匹配 (如果我们猜测出了字段类型，检查用户键是否属于同一类型)
                if not best_match and guessed_type:
                    for key_word in field_types.get(guessed_type, []):
                        if key_word in user_key_lower:
                            logger.info(f"部分匹配字段: {user_key} -> {field_selector} (通过 field)")
                            best_match = user_key
                            break
                    if best_match:
                        continue
                
                # 对于email类型，特殊处理
                if not best_match and field_type == "email" and "email" in user_key_lower:
                    logger.info(f"部分匹配字段: {user_key} -> {field_selector} (通过 email)")
                    best_match = user_key
                    continue
            
            # 如果找到了匹配项，将用户数据映射到表单字段
            if best_match:
                mapped_data[field_selector] = user_data[best_match]
            # 如果是email字段但没找到匹配，可以尝试特殊处理
            elif field_type == "email" and "email" in user_data:
                mapped_data[field_selector] = user_data["email"]
            
        logger.info(f"表单映射完成, 原始字段数: {len(user_data)}, 映射后字段数: {len(mapped_data)}")
        
        # 输出映射结果
        for field, value in mapped_data.items():
            logger.info(f"映射字段: {field} -> {value}")
        
        return mapped_data
    
    async def fill_form(self, form_selector: str, field_data: Dict[str, str]) -> bool:
        """填写表单字段"""
        logger.info("开始填写表单...")
        logger.info(f"等待表单元素加载，尝试多种选择器，超时时间{self.timeout//1000}秒...")
        
        # 尝试不同的表单选择器
        form_selectors_to_try = [form_selector, "form", ".form", "#contact-form", ".contact-form"]
        found_form = False
        
        for selector in form_selectors_to_try:
            try:
                logger.info(f"尝试选择器: {selector}")
                is_visible = await self.page.is_visible(selector, timeout=10000)
                if is_visible:
                    logger.info(f"找到表单元素，使用选择器: {selector}")
                    found_form = True
                    
                    # 在表单中填写字段
                    for field_selector, value in field_data.items():
                        try:
                            # 查看字段是否存在
                            field_exists = await self.page.is_visible(field_selector, timeout=5000)
                            if field_exists:
                                field_type = await self.page.evaluate(f"""
                                    () => {{
                                        const el = document.querySelector("{field_selector}");
                                        if (!el) return null;
                                        return el.type || el.tagName.toLowerCase();
                                    }}
                                """)
                                
                                logger.info(f"填写字段: {field_selector}, 类型: {field_type}, 值: {value}...")
                                
                                # 根据字段类型处理
                                if field_type == "select" or field_type == "SELECT":
                                    # 处理下拉菜单
                                    await self.page.select_option(field_selector, value)
                                elif field_type == "checkbox":
                                    # 处理复选框
                                    if value.lower() in ["true", "yes", "1", "on"]:
                                        await self.page.check(field_selector)
                                    else:
                                        await self.page.uncheck(field_selector)
                                elif field_type == "radio":
                                    # 处理单选按钮
                                    await self.page.check(field_selector)
                                elif field_type == "textarea" or field_type == "TEXTAREA":
                                    # 处理文本区域
                                    await self.page.fill(field_selector, value)
                                else:
                                    # 处理常规输入字段
                                    await self.page.fill(field_selector, value)
                                
                                # 随机延迟，模拟人类操作
                                await asyncio.sleep(0.5)
                                
                            else:
                                logger.warning(f"未找到字段: {field_selector}")
                        except Exception as e:
                            logger.error(f"填写字段 {field_selector} 时出错: {str(e)}")
                    
                    logger.info("表单填写成功")
                    return True
                else:
                    logger.info(f"选择器 {selector} 未找到表单元素，尝试下一个")
            except Exception as e:
                logger.error(f"使用选择器 {selector} 填写表单时出错: {str(e)}")
        
        if not found_form:
            logger.error("无法找到或填写表单")
            return False
    
    async def submit_form(self, form_selector: str, wait_for_navigation: bool = True) -> Tuple[bool, str]:
        """提交表单并处理结果"""
        try:
            # 检查是否存在验证码
            captcha_detected = await self.check_captcha()
            if captcha_detected:
                logger.error("检测到验证码，无法自动提交表单")
                return False, "验证码检测"
            
            logger.info("准备提交表单...")
            
            # 查找提交按钮
            submit_button = await self.find_submit_button(form_selector)
            if not submit_button:
                logger.error("未找到表单提交按钮")
                return False, "未找到提交按钮"
            
            logger.info(f"找到提交按钮: {submit_button}")
            
            # 点击提交按钮
            logger.info("点击提交按钮...")
            
            # 准备监听导航事件
            if wait_for_navigation:
                # 使用Promise.race获取先发生的事件
                navigation_promise = self.page.wait_for_navigation(timeout=self.timeout, wait_until="domcontentloaded")
                
                # 点击提交按钮
                await self.page.click(submit_button)
                
                try:
                    # 等待导航完成
                    await navigation_promise
                    logger.info("表单提交后导航完成")
                except PlaywrightTimeoutError:
                    logger.error(f"提交表单超时: Timeout {self.timeout}ms exceeded.")
                    return False, "提交超时"
            else:
                # 直接点击提交按钮，不等待导航
                await self.page.click(submit_button)
                # 等待一段时间让客户端处理
                await asyncio.sleep(3)
            
            # 检查提交结果
            success, message = await self.check_submission_result()
            
            return success, message
            
        except Exception as e:
            logger.error(f"提交表单时出错: {str(e)}")
            return False, str(e)
    
    async def check_submission_result(self) -> Tuple[bool, str]:
        """检查表单提交结果"""
        try:
            # 等待页面稳定
            await asyncio.sleep(2)
            
            # 检查常见的成功消息
            success_selectors = [
                "text='Thank you'", 
                "text='Thanks'",
                "text='Success'",
                "text='Submitted'",
                "text='Received'",
                "text='提交成功'",
                "text='谢谢'",
                "text='已收到'",
                ".success",
                ".success-message",
                ".thank-you",
                ".confirmation"
            ]
            
            for selector in success_selectors:
                try:
                    success = await self.page.is_visible(selector, timeout=3000)
                    if success:
                        message = await self.page.text_content(selector)
                        logger.info(f"检测到成功消息: {message}")
                        return True, message or "提交成功"
                except Exception:
                    pass
            
            # 检查常见的错误消息
            error_selectors = [
                ".error", 
                ".error-message",
                "[class*='error']",
                "text='Error'",
                "text='Failed'",
                "text='错误'",
                "text='失败'"
            ]
            
            for selector in error_selectors:
                try:
                    error = await self.page.is_visible(selector, timeout=3000)
                    if error:
                        message = await self.page.text_content(selector)
                        logger.error(f"检测到错误消息: {message}")
                        return False, message or "提交失败"
                except Exception:
                    pass
            
            # 没有明确指示时，查看URL变化
            current_url = self.page.url
            if "thank" in current_url or "success" in current_url or "confirmation" in current_url:
                logger.info(f"从URL判断提交成功: {current_url}")
                return True, "根据URL判断提交成功"
            
            # 检查页面标题中是否包含感谢词
            title = await self.page.title()
            if "thank" in title.lower() or "success" in title.lower() or "confirmation" in title.lower():
                logger.info(f"从标题判断提交成功: {title}")
                return True, "根据标题判断提交成功"
            
            # 默认返回假定成功，因为部分网站可能没有明确的成功提示
            logger.info("未检测到明确的成功或失败指示，假定提交成功")
            return True, "未检测到明确结果，假定成功"
        
        except Exception as e:
            logger.error(f"检查提交结果时出错: {str(e)}")
            return False, str(e)
    
    async def check_captcha(self) -> bool:
        """检查页面是否含有验证码"""
        logger.info("检查页面中是否存在验证码...")
        
        captcha_selectors = [
            "iframe[src*='recaptcha']",
            "iframe[src*='captcha']",
            ".g-recaptcha",
            "[class*='captcha']",
            "[id*='captcha']",
            "img[src*='captcha']"
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

# 使用示例
async def example_usage(page):
    form_helper = FormHelper(page)
    
    # 查找表单
    form_selector = await form_helper.find_form()
    if form_selector:
        # 获取表单字段
        form_fields = await form_helper.get_form_fields(form_selector)
        
        # 假设我们有用户数据
        user_data = {
            "product_name": "测试产品",
            "email": "test@example.com",
            "product_url": "https://example.com",
            "description": "这是一个测试产品描述"
        }
        
        # 映射用户数据到表单字段
        mapped_data = await form_helper.map_form_fields(user_data, form_fields)
        
        # 填写表单
        if await form_helper.fill_form(form_selector, mapped_data):
            # 提交表单
            success, message = await form_helper.submit_form(form_selector)
            logger.info(f"表单提交结果: {'成功' if success else '失败'}, 消息: {message}")
    else:
        logger.error("未找到表单") 