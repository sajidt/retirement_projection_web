"""AI chat functionality using Ollama with financial context."""

import requests
from typing import List, Dict, Any
import streamlit as st


def build_financial_context(
    portfolio_data: Dict[str, Any],
    cash_cad: float,
    cash_usd: float,
    age: int,
    annual_spend: float,
    holdings_df: Any = None
) -> str:
    """
    Build a comprehensive financial context string for the AI.
    
    Args:
        portfolio_data: Dictionary with portfolio summary information
        cash_cad: Cash in CAD
        cash_usd: Cash in USD
        age: Current age
        annual_spend: Annual spending amount
        holdings_df: Optional DataFrame with holdings details
    
    Returns:
        str: Formatted financial context
    """
    context = f"""
PERSONAL FINANCIAL PROFILE:
- Age: {age} years old
- Annual Spending: ${annual_spend:,.2f}

PORTFOLIO SUMMARY:
- Total Investments: ${portfolio_data.get('total_investments', 0):,.2f}
- Cash (CAD): ${cash_cad:,.2f}
- Cash (USD): ${cash_usd:,.2f}
- Total Net Worth: ${portfolio_data.get('total_investments', 0) + cash_cad:,.2f}

ASSET ALLOCATION:
- Domestic Stock (Canadian): ${portfolio_data.get('total_canadian_stock', 0):,.2f}
- US Stock: ${portfolio_data.get('total_domestic_stock', 0):,.2f}
- International Stock: ${portfolio_data.get('total_intl_stock', 0):,.2f}
- Bonds: ${portfolio_data.get('total_bond', 0):,.2f}

PORTFOLIO METRICS:
- Weighted Average Return: {portfolio_data.get('weighted_average', 0) * 100:.2f}%
- Expense Ratio (Net): {portfolio_data.get('expense_ratio_net', 0):.2f}%
"""
    
    if holdings_df is not None:
        context += "\nTOP HOLDINGS:\n"
        top_holdings = holdings_df.nlargest(10, 'MarketValueCAD')
        for idx, row in top_holdings.iterrows():
            context += f"- {row['Name']}: {row['Quantity']} shares @ ${row['Price']:.2f} = ${row['MarketValueCAD']:,.2f}\n"
    
    return context


def initialize_chat_session():
    """Initialize Streamlit session state for chat."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "financial_context" not in st.session_state:
        st.session_state.financial_context = ""


def set_financial_context(context: str):
    """Set the financial context in session state."""
    st.session_state.financial_context = context


def query_ollama(conversation: List[Dict[str, str]]) -> str:
    """
    Send conversation to Ollama and get response.
    
    Args:
        conversation: List of message dicts with 'role' and 'content'
    
    Returns:
        str: The AI response
    """
    # Build the prompt from conversation
    prompt = ""
    for msg in conversation:
        role = msg.get("role", "").capitalize()
        content = msg.get("content", "")
        if role == "System":
            prompt += f"System: {content}\n\n"
        elif role == "User":
            prompt += f"User: {content}\n\n"
        elif role == "Assistant":
            prompt += f"Assistant: {content}\n\n"
    
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3-chatqa:latest",  # You can change to other models like llama3, mistral, neural-chat
                "prompt": prompt,
                "stream": False
            },
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("response", "No response").strip()
        else:
            return f"Error: {response.status_code} - {response.text}"
    except requests.exceptions.RequestException as e:
        return f"Error connecting to Ollama: {e}. Make sure Ollama is running on localhost:11434."


def chat_with_ai(
    user_message: str,
    portfolio_data: Dict[str, Any] = None,
    cash_cad: float = 0,
    cash_usd: float = 0,
    age: int = 0,
    annual_spend: float = 0,
    holdings_df: Any = None
) -> str:
    """
    Process a user message and get AI response with financial context.
    
    Args:
        user_message: The user's message
        portfolio_data: Portfolio summary data
        cash_cad: Cash in CAD
        cash_usd: Cash in USD
        age: User's age
        annual_spend: Annual spending
        holdings_df: Holdings DataFrame
    
    Returns:
        str: The AI's response
    """
    # Initialize session if needed
    initialize_chat_session()
    
    # Update financial context if provided
    if portfolio_data and age and annual_spend:
        context = build_financial_context(
            portfolio_data, cash_cad, cash_usd, age, annual_spend, holdings_df
        )
        set_financial_context(context)
    
    # Build system prompt with financial context
    system_prompt = f"""You are an expert financial advisor specializing in retirement planning, investment strategy, and personal finance.

You have access to the following client's financial information:

{st.session_state.financial_context}

Provide thoughtful, data-driven advice based on this information. Be specific and reference their actual holdings and portfolio metrics when relevant.
Be conversational and helpful. Explain financial concepts clearly."""
    
    # Build conversation history
    conversation = [
        {"role": "system", "content": system_prompt}
    ]
    
    # Add previous messages from session
    if "messages" in st.session_state:
        for msg in st.session_state.messages:
            conversation.append({"role": msg["role"], "content": msg["content"]})
    
    # Add current user message
    conversation.append({"role": "user", "content": user_message})
    
    # Get response from Ollama
    ai_response = query_ollama(conversation)
    
    # Store in session state
    st.session_state.messages.append({"role": "user", "content": user_message})
    st.session_state.messages.append({"role": "assistant", "content": ai_response})
    
    return ai_response


def render_chat_interface(
    portfolio_data: Dict[str, Any] = None,
    cash_cad: float = 0,
    cash_usd: float = 0,
    age: int = 0,
    annual_spend: float = 0,
    holdings_df: Any = None
):
    """
    Render the chat interface in Streamlit.
    
    Args:
        portfolio_data: Portfolio summary data
        cash_cad: Cash in CAD
        cash_usd: Cash in USD
        age: User's age
        annual_spend: Annual spending
        holdings_df: Holdings DataFrame
    """
    initialize_chat_session()
    
    # Set financial context once
    if portfolio_data and age and annual_spend and not st.session_state.financial_context:
        context = build_financial_context(
            portfolio_data, cash_cad, cash_usd, age, annual_spend, holdings_df
        )
        set_financial_context(context)
    
    st.header("💬 Financial Advisor Chat")
    
    st.info(
        "Ask me anything about your finances, investment strategy, or retirement planning. "
        "I have access to your complete financial profile and can provide personalized advice."
    )
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # Chat input
    if user_input := st.chat_input("Ask about your finances..."):
        with st.chat_message("user"):
            st.write(user_input)
        
        with st.spinner("Thinking..."):
            response = chat_with_ai(
                user_input,
                portfolio_data=portfolio_data,
                cash_cad=cash_cad,
                cash_usd=cash_usd,
                age=age,
                annual_spend=annual_spend,
                holdings_df=holdings_df
            )
        
        with st.chat_message("assistant"):
            st.write(response)


def clear_chat_history():
    """Clear the chat history."""
    st.session_state.messages = []
