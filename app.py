import streamlit as st
import google.generativeai as genai
import pandas as pd
import time
import re

# Настройка страницы
st.set_page_config(page_title="Bulk Lead Gen AI", layout="wide")
st.title("Bulk B2B Lead Gen & CustDev Assistant")

# Добавляем блок с правилами и описанием
st.markdown("""
### 📌 Правила заполнения:
* **[PRODUCT_DETAILS]:** Здесь описываешь текущий функционал, например: *MCP data gateway, secure chatbot connectors for corporate data, etc.*
* **[TARGET_AUDIENCE]:** Кого ищем: *CTO, CISO, Founders*. ЕСЛИ ПУСТО ИЛИ НЕ ЗНАЕШЬ — напиши **"Suggest ICP"**
---
""")

# Настройка API ключа
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API ключ не найден. Добавьте его в настройки Streamlit (Secrets).")
    st.stop()

# Интерфейс для ввода данных
col1, col2 = st.columns(2)
with col1:
    product_details = st.text_area("Product Details", "MCP data gateway, secure chatbot connectors...")
with col2:
    target_audience = st.text_input("Target Audience", "Suggest ICP")

# Загрузка таблицы
uploaded_file = st.file_uploader("Загрузи выгрузку постов из Apify (формат CSV)", type=["csv"])

if uploaded_file is not None:
    # Читаем CSV
    df = pd.read_csv(uploaded_file)
    st.write("Превью загруженных данных:")
    st.dataframe(df.head(3))
    
    # Выбор колонки
    text_column = st.selectbox("Выбери колонку, в которой находится текст поста (обычно text или content):", df.columns)
    
    if st.button("🚀 Сгенерировать сообщения для всех лидов"):
        model = genai.GenerativeModel('gemini-1.5-flash')
        results = []
        
        progress_text = "Обрабатываем лидов..."
        my_bar = st.progress(0, text=progress_text)
        total_rows = len(df)
        
        for index, row in df.iterrows():
            lead_text = str(row[text_column])
            
            if pd.isna(row[text_column]) or lead_text.strip() == "":
                results.append("Нет данных для анализа")
                my_bar.progress((index + 1) / total_rows, text=f"Обработано {index + 1} из {total_rows}")
                continue
                
            PROMPT = f"""
            Act as an expert B2B Founder & Lead Gen Strategist doing Customer Discovery. My name is Slava. 

            Here is my current context:
            [PRODUCT_DETAILS]: {product_details}
            [TARGET_AUDIENCE]: {target_audience}

            Here is the text/post from the target lead:
            "{lead_text}"

            Step 1: Lead Analysis (in Russian)
            - Relevance Score: [Оцени от 1 до 10. Формат СТРОГО: "Relevance Score: X/10"]
            - The Technical Hook: What specific phrase or problem from their text we can use.

            Step 2: Outreach Drafts (in English)
            STRICT ANTI-AI STYLE RULES:
            - Zero exclamation marks. Use periods.
            - No corporate fluff, fake enthusiasm, or standard AI greetings.
            - Sentences must be short, slightly informal, like a founder typing quickly on a phone.
            - Goal: Customer Discovery. Ask for a "reality check" or "blunt feedback". DO NOT pitch. 
            - Request a 10-15 minute chat.

            Generate:
            1. Invite Note (under 200 chars).
            2. Direct Message (Subject line lowercase. 3-4 short sentences max).
            3. 2 options for a LinkedIn Comment (All lowercase. NO fake enthusiasm. Just validate the pain point).
            """
            
            try:
                time.sleep(3) # Пауза от лимитов
                response = model.generate_content(PROMPT)
                results.append(response.text)
            except Exception as e:
                results.append(f"Ошибка API: {e}")
                
            my_bar.progress((index + 1) / total_rows, text=f"Обработано {index + 1} из {total_rows}")
            
        df['AI_Analysis_and_Drafts'] = results
        st.success("✅ Анализ завершен!")
        
        # ВЫВОД КАРТОЧЕК ЛИДОВ НА ЭКРАН
        st.subheader("🔥 Топ отобранных лидов")
        
        for index, row in df.iterrows():
            analysis_text = str(row.get('AI_Analysis_and_Drafts', ''))
            post_text = str(row.get(text_column, ''))
            
            # Регулярное выражение для вытаскивания Score
            score = "N/A"
            match = re.search(r'Relevance Score:\s*(\d+)', analysis_text, re.IGNORECASE)
            if match:
                score = match.group(1)
                
            # Отрисовка раскрывающегося блока
            with st.expander(f"Лид #{index+1} | Score: {score}/10"):
                col_left, col_right = st.columns([1, 1.5]) # Левая колонка уже, правая шире
                
                with col_left:
                    st.info("📝 **Исходный пост/текст:**")
                    st.write(post_text)
                    
                with col_right:
                    st.success("🤖 **Анализ и Драфты:**")
                    st.write(analysis_text)
        
        # Кнопка для скачивания файла в самом низу
        st.markdown("---")
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 Скачать результат таблицей (CSV)",
            data=csv,
            file_name='processed_leads.csv',
            mime='text/csv',
        )
