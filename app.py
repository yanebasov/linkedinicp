import streamlit as st
import google.generativeai as genai
import pandas as pd
import time
import re

# 1. Настройка страницы
st.set_page_config(page_title="Provenyx Lead Gen", layout="wide")
st.title("Bulk B2B Lead Gen & CustDev Assistant")

# 2. API Конфигурация
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("API ключ не найден. Проверь Secrets в Streamlit.")
    st.stop()

# 3. Поля ввода
col1, col2 = st.columns(2)
with col1:
    product_details = st.text_area("Product Details", "Provenyx: multi-LLM governance, гранулярные разрешения на уровне файлов.")
with col2:
    target_audience = st.text_input("Target Audience", "COO, Head of Marketing, CISO")

uploaded_file = st.file_uploader("Загрузи CSV", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    available_cols = df.columns.tolist()
    text_column = st.selectbox("Текст поста:", available_cols, 
                               index=available_cols.index('text') if 'text' in available_cols else 0)
    
    url_col = next((c for c in ['url', 'postUrl'] if c in available_cols), None)
    author_url_col = next((c for c in ['authorProfileUrl', 'authorUrl'] if c in available_cols), None)

    if st.button("🚀 Начать анализ"):
        # Пытаемся найти модель Gemini 3 через список доступных моделей
        try:
            available_models = [m.name for m in genai.list_models()]
            # Ищем сначала 3-ю версию, потом 1.5 как запасную
            model_id = next((m for m in available_models if "gemini-3" in m), "gemini-1.5-flash")
            model = genai.GenerativeModel(model_id)
        except:
            model = genai.GenerativeModel('gemini-1.5-flash')

        results, scores = [], []
        progress_bar = st.progress(0)
        
        for index, row in df.iterrows():
            lead_text = str(row[text_column])
            if pd.isna(row[text_column]) or lead_text.strip() in ["", "nan"]:
                results.append("Нет данных"); scores.append(0)
                continue
                
            PROMPT = f"""
            Act as an expert B2B Lead Gen Strategist. Product: {product_details}. 
            Audience: {target_audience}. Lead Post: "{lead_text}"
            Analyze in Russian: Relevance Score: [X/10].
            Write Outreach in English: 1 Invite Note, 1 DM, 2 LinkedIn Comments (lowercase).
            """
            
            try:
                time.sleep(1) # Защита от лимитов
                response = model.generate_content(PROMPT)
                output = response.text
                score_match = re.search(r'Score:\s*(\d+)', output, re.IGNORECASE)
                scores.append(int(score_match.group(1)) if score_match else 0)
                results.append(output)
            except Exception as e:
                results.append(f"Ошибка: {e}"); scores.append(0)
            progress_bar.progress((index + 1) / len(df))
            
        df['Score'] = scores
        df['AI_Analysis'] = results
        df = df.sort_values(by='Score', ascending=False)
        
        st.success("✅ Готово!")
        for index, row in df.iterrows():
            p_url = row.get(url_col, "#"); a_url = row.get(author_url_col, "#")
            with st.expander(f"Лид #{index+1} | Score: {row['Score']}/10"):
                st.markdown(f"🔗 [Пост]({p_url}) | 👤 [Автор]({a_url})")
                st.write(row['AI_Analysis'])

        st.download_button("💾 Скачать CSV", df.to_csv(index=False).encode('utf-8'), "leads_scored.csv")
