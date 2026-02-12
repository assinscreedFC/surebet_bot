# Dashboard Streamlit

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import asyncio
import sys
from pathlib import Path

# Ajouter le dossier parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.database import Database
from config import DB_FILE


@st.cache_resource
def get_database():
    """Crée et retourne une connexion DB mise en cache."""
    db = Database(DB_FILE)
    return db

@st.cache_data(ttl=30)  # Cache de 30 secondes
def load_data_cached():
    """Charge les données avec cache pour améliorer les performances."""
    async def _load():
        db = get_database()
        await db.connect()
        try:
            surebets = await db.get_surebets(limit=500)
            stats = await db.get_stats()
            logs = await db.get_logs(limit=200)
            api_usage = await db.get_api_usage(limit=100)
            return {
                "surebets": surebets,
                "stats": stats,
                "logs": logs,
                "api_usage": api_usage
            }
        finally:
            await db.close()
    
    # Utiliser asyncio.run() au lieu de créer une nouvelle boucle
    return asyncio.run(_load())


def main():
    st.set_page_config(
        page_title="Bot Surebet VDO Group",
        page_icon="🎯",
        layout="wide"
    )
    
    # Header
    st.title("🎯 Bot Surebet VDO Group")
    st.markdown("---")
    
    # Charger les données avec cache
    try:
        data = load_data_cached()
    except Exception as e:
        st.error(f"Erreur chargement données: {e}")
        import traceback
        st.exception(e)
        data = {"surebets": [], "stats": {}, "logs": [], "api_usage": []}
    
    # === MÉTRIQUES PRINCIPALES ===
    col1, col2, col3, col4 = st.columns(4)
    
    stats = data.get("stats", {})
    
    with col1:
        st.metric(
            label="📊 Surebets Détectés",
            value=stats.get("total_surebets", 0)
        )
    
    with col2:
        st.metric(
            label="📈 Profit Total",
            value=f"{stats.get('total_profit_pct', 0):.2f}%"
        )
    
    with col3:
        api_usage = data.get("api_usage", [])
        remaining = api_usage[0].get("requests_remaining", "N/A") if api_usage else "N/A"
        st.metric(
            label="📡 Requêtes API Restantes",
            value=remaining
        )
    
    with col4:
        st.metric(
            label="🔑 Clés API Actives",
            value="1"  # À mettre à jour dynamiquement
        )
    
    st.markdown("---")
    
    # === TABS ===
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Surebets Récents", 
        "📊 Statistiques", 
        "📈 Usage API",
        "📝 Logs"
    ])
    
    # === TAB 1: SUREBETS ===
    with tab1:
        st.subheader("Dernières Opportunités Détectées")
        
        surebets = data.get("surebets", [])
        
        if surebets:
            df = pd.DataFrame(surebets)
            
            # Filtres
            col1, col2 = st.columns(2)
            with col1:
                sport_filter = st.selectbox(
                    "Filtrer par sport",
                    ["Tous"] + list(df["sport"].unique())
                )
            with col2:
                min_profit = st.slider("Profit minimum (%)", 0.0, 10.0, 0.0, 0.1)
            
            # Appliquer filtres
            if sport_filter != "Tous":
                df = df[df["sport"] == sport_filter]
            df = df[df["profit_pct"] >= min_profit]
            
            # Afficher
            st.dataframe(
                df[[
                    "detected_at", "sport", "league", "match", "market",
                    "bookmaker1", "odds1", "bookmaker2", "odds2",
                    "profit_pct", "profit_base_100"
                ]].rename(columns={
                    "detected_at": "Date",
                    "sport": "Sport",
                    "league": "Ligue",
                    "match": "Match",
                    "market": "Marché",
                    "bookmaker1": "Bookmaker 1",
                    "odds1": "Cote 1",
                    "bookmaker2": "Bookmaker 2",
                    "odds2": "Cote 2",
                    "profit_pct": "Profit %",
                    "profit_base_100": "Gain/100€"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Aucun surebet détecté pour le moment")
    
    # === TAB 2: STATISTIQUES ===
    with tab2:
        st.subheader("Analyse des Performances")
        
        col1, col2 = st.columns(2)
        
        # Par sport
        with col1:
            st.markdown("### 📊 Répartition par Sport")
            by_sport = stats.get("by_sport", [])
            if by_sport:
                df_sport = pd.DataFrame(by_sport)
                fig = px.pie(
                    df_sport, 
                    values="count", 
                    names="sport",
                    title="Volume par Sport"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Pas de données")
        
        # Par marché
        with col2:
            st.markdown("### 📈 Top Marchés")
            by_market = stats.get("by_market", [])
            if by_market:
                df_market = pd.DataFrame(by_market)
                fig = px.bar(
                    df_market,
                    x="market",
                    y="avg_profit",
                    title="Profit Moyen par Marché (%)"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Pas de données")
        
        # Tendances temporelles
        st.markdown("### 📅 Tendances Temporelles")
        surebets = data.get("surebets", [])
        if surebets:
            df = pd.DataFrame(surebets)
            df["detected_at"] = pd.to_datetime(df["detected_at"])
            df["date"] = df["detected_at"].dt.date
            
            daily = df.groupby("date").agg({
                "id": "count",
                "profit_pct": "sum"
            }).reset_index()
            daily.columns = ["Date", "Nombre", "Profit Total"]
            
            fig = go.Figure()
            fig.add_trace(go.Bar(x=daily["Date"], y=daily["Nombre"], name="Surebets"))
            fig.add_trace(go.Scatter(x=daily["Date"], y=daily["Profit Total"], name="Profit %", yaxis="y2"))
            
            fig.update_layout(
                title="Volume et Profit Quotidiens",
                yaxis=dict(title="Nombre de Surebets"),
                yaxis2=dict(title="Profit Total %", overlaying="y", side="right")
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # === TAB 3: USAGE API ===
    with tab3:
        st.subheader("Consommation API")
        
        api_usage = data.get("api_usage", [])
        if api_usage:
            df = pd.DataFrame(api_usage)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            
            fig = px.line(
                df,
                x="timestamp",
                y="requests_remaining",
                title="Évolution du Quota API"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(
                df[["timestamp", "api_key", "requests_used", "requests_remaining"]],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Pas de données d'usage API")
    
    # === TAB 4: LOGS ===
    with tab4:
        st.subheader("Logs du Bot")
        
        col1, col2 = st.columns([1, 4])
        with col1:
            level_filter = st.selectbox(
                "Niveau",
                ["Tous", "INFO", "WARNING", "ERROR"]
            )
        
        logs = data.get("logs", [])
        if logs:
            df = pd.DataFrame(logs)
            
            if level_filter != "Tous":
                df = df[df["level"] == level_filter]
            
            # Colorer par niveau
            def color_level(level):
                colors = {
                    "INFO": "🟢",
                    "WARNING": "🟡", 
                    "ERROR": "🔴"
                }
                return colors.get(level, "⚪")
            
            df["icon"] = df["level"].apply(color_level)
            df["display"] = df["icon"] + " " + df["level"]
            
            st.dataframe(
                df[["timestamp", "display", "message"]].rename(columns={
                    "timestamp": "Date",
                    "display": "Niveau",
                    "message": "Message"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Pas de logs disponibles")
    
    # Footer
    st.markdown("---")
    st.markdown("**VDO Group** | Bot Surebet v1.0")


if __name__ == "__main__":
    main()
