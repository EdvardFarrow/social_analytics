from django.conf import settings
import google.generativeai as genai


def get_gemini_model():
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY не найден в настройках.")
    
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    return model


def generate_content_summary(prompt):
    try:
        model = get_gemini_model()
        response = model.generate_content(prompt)
        return response.text
    except ValueError as e:
        print(f"Ошибка: {e}")
        return "Ошибка: API ключ не настроен."
    except Exception as e:
        print(f"Ошибка при генерации контента: {e}")
        return "Ошибка при генерации контента."