import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine
import sys
import os

# Importar config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import POSTGRES_CONFIG

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Executive Dashboard", layout="wide", page_icon="📊")

# --- 2. ESTILOS CSS (Diseño Corporativo Ajustado) ---
st.markdown("""
<style>
    /* FONDO GENERAL */
    .stApp {
        background-color: #F4F7F6;
    }

    /* KPI CARDS */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #E0E0E0;
        padding: 10px 15px;
        border-radius: 8px;
        border-left: 6px solid #003366; 
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        min-height: 100px;
    }
    div[data-testid="stMetricLabel"] {
        color: #666;
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 5px;
    }
    div[data-testid="stMetricValue"] {
        color: #003366;
        font-size: 20px !important;
        font-weight: 800;
        line-height: 1.2;
    }

    /* ESTILOS PARA TABLAS HTML PERSONALIZADAS */
    .styled-table {
        border-collapse: collapse;
        margin: 10px 0;
        font-size: 12px;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        width: 100%;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        border-radius: 6px;
        overflow: hidden;
    }
    .styled-table thead tr {
        background-color: #003366; 
        color: #ffffff;
        text-align: left;
        font-weight: bold;
    }
    .styled-table th, .styled-table td {
        padding: 10px 12px;
    }
    .styled-table tbody tr {
        border-bottom: 1px solid #dddddd;
        background-color: #ffffff;
        color: #333333;
    }
    .styled-table tbody tr:nth-of-type(even) {
        background-color: #f8f9fa; 
    }
    .styled-table tbody tr:last-of-type {
        border-bottom: 3px solid #003366;
        font-weight: bold;
        background-color: #eef2f5;
    }
    
    /* TITULOS */
    h1, h2, h3 {
        color: #003366 !important;
        font-family: 'Segoe UI', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER PERSONALIZADO ---
st.markdown("<h2 style='text-align: left; color: #003366;'>📊 Monitor de Desempeño Comercial</h2>", unsafe_allow_html=True)
st.markdown("---")

# --- 3. CARGA DE DATOS ---
@st.cache_data(ttl=60)
def load_data():
    conn_str = f"postgresql+psycopg2://{POSTGRES_CONFIG['user']}:{POSTGRES_CONFIG['password']}@{POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}/{POSTGRES_CONFIG['database']}"
    engine = create_engine(conn_str)
    schema = POSTGRES_CONFIG['schema']
    query = f"SELECT * FROM {schema}.fact_comparativa_precios"
    df = pd.read_sql(query, engine)
    return df

try:
    df = load_data()
    
    if df.empty:
        st.warning("No hay datos cargados.")
    else:
        # Cálculos
        df['monto_descuento_total'] = df.apply(
            lambda x: (x['diferencia_mt2'] * x['mt2']) if x['diferencia_mt2'] < -0.01 else 0, axis=1
        )
        df['es_esquina'] = df['categoria'].astype(str).str.upper().str.contains('ESQ.').astype(int)
        df['tiene_descuento'] = df['glosa'].apply(lambda x: 1 if x == 'DESCUENTO' else 0)
        
        if 'contract_date' in df.columns:
            df['contract_date'] = pd.to_datetime(df['contract_date'])
            # Creamos columna de fecha str para el gráfico categórico
            df['fecha_str'] = df['contract_date'].dt.strftime('%d-%b')
        
        if 'tipo_via' in df.columns:
            df['tipo_via'] = df['tipo_via'].replace('AVENIDA PAVIMENTADA', 'AV. PAVIMENTADA')

        # --- FILTROS ---
        with st.sidebar:
            st.markdown("### 🎛️ Filtros")
            urb_opts = ['Todas'] + sorted(list(df['urbanizacion'].unique()))
            sel_urb = st.selectbox("Urbanización", urb_opts)
            
            estado_opts = ['Todos'] + sorted(list(df['estado_contrato'].unique()))
            sel_estado = st.selectbox("Estado", estado_opts)
            
            filter_date = False
            if st.checkbox("Filtrar por Fecha", value=False):
                min_date = df['contract_date'].min().date()
                max_date = df['contract_date'].max().date()
                date_range = st.date_input("Rango", [min_date, max_date])
                filter_date = True

        df_filtered = df.copy()
        if sel_urb != 'Todas':
            df_filtered = df_filtered[df_filtered['urbanizacion'] == sel_urb]
        if sel_estado != 'Todos':
            df_filtered = df_filtered[df_filtered['estado_contrato'] == sel_estado]
        if filter_date and len(date_range) == 2:
             mask = (df_filtered['contract_date'].dt.date >= date_range[0]) & (df_filtered['contract_date'].dt.date <= date_range[1])
             df_filtered = df_filtered[mask]

        # --- KPIs ---
        total_qty = len(df_filtered)
        t_desc_qty = df_filtered['tiene_descuento'].sum()
        pct_desc = (t_desc_qty / total_qty * 100) if total_qty > 0 else 0
        t_venta = df_filtered['valor_contado'].sum()
        t_desc_usd = df_filtered['monto_descuento_total'].sum()

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Unidades", f"{total_qty}")
        c2.metric("Con Desc.", f"{t_desc_qty}")
        # CAMBIO AQUÍ: Nombre de etiqueta ajustado
        c3.metric("% con desc.", f"{pct_desc:.1f}%")
        c4.metric("Venta Total", f"${t_venta:,.0f}")
        c5.metric("Monto Desc.", f"${t_desc_usd:,.0f}", delta_color="inverse")

        st.markdown("<br>", unsafe_allow_html=True)

        # --- GENERADOR DE TABLA HTML ---
        def render_html_table(df_in, columna_agrupadora, titulo_columna):
            if df_in.empty: return ""
            
            resumen = df_in.groupby(columna_agrupadora).agg(
                Cantidad=('nro_contract', 'count'),
                Cant_Esq=('es_esquina', 'sum'),
                Cant_Desc=('tiene_descuento', 'sum'),
                Monto_Desc=('monto_descuento_total', 'sum'),
                Venta_Total=('valor_contado', 'sum')
            ).reset_index()
            
            qty_g = resumen['Cantidad'].sum()
            esq_g = resumen['Cant_Esq'].sum()
            desc_g = resumen['Cant_Desc'].sum()
            mdesc_g = resumen['Monto_Desc'].sum()
            venta_g = resumen['Venta_Total'].sum()
            
            resumen['Promedio'] = resumen['Venta_Total'] / resumen['Cantidad']
            resumen['Part'] = (resumen['Cantidad'] / qty_g * 100) if qty_g > 0 else 0
            resumen = resumen.sort_values('Venta_Total', ascending=False)
            
            fila_total = pd.DataFrame([{
                columna_agrupadora: 'TOTAL',
                'Cantidad': qty_g, 'Cant_Esq': esq_g, 'Cant_Desc': desc_g,
                'Monto_Desc': mdesc_g, 'Venta_Total': venta_g,
                'Promedio': (venta_g/qty_g) if qty_g > 0 else 0, 'Part': 100.0
            }])
            final_df = pd.concat([resumen, fila_total], ignore_index=True)
            
            # HTML
            html = '<table class="styled-table">'
            html += f'<thead><tr>'
            html += f'<th>{titulo_columna}</th><th>Cant.</th><th>Esq.</th><th>C. Desc</th>'
            html += f'<th>Desc ($)</th><th>Venta Total ($)</th><th>Prom. ($)</th><th>% Part</th>'
            html += '</tr></thead><tbody>'
            
            for _, row in final_df.iterrows():
                name = row[columna_agrupadora]
                monto_desc = f"${abs(row['Monto_Desc']):,.0f}"
                venta = f"${row['Venta_Total']:,.0f}"
                prom = f"${row['Promedio']:,.0f}"
                part = f"{row['Part']:.1f}%"
                
                html += f"<tr>"
                html += f"<td>{name}</td>"
                html += f"<td>{int(row['Cantidad'])}</td>"
                html += f"<td>{int(row['Cant_Esq'])}</td>"
                html += f"<td>{int(row['Cant_Desc'])}</td>"
                html += f"<td>{monto_desc}</td>"
                html += f"<td>{venta}</td>"
                html += f"<td>{prom}</td>"
                html += f"<td>{part}</td>"
                html += f"</tr>"
                
            html += '</tbody></table>'
            return html

        # Generar HTMLs
        html_vias = render_html_table(df_filtered, 'tipo_via', 'Categoría Vía')
        html_zonas = render_html_table(df_filtered, 'zona', 'Zona')

        st.subheader("Análisis Detallado por Vía")
        st.markdown(html_vias, unsafe_allow_html=True)
        
        st.subheader("Análisis Detallado por Zona")
        st.markdown(html_zonas, unsafe_allow_html=True)

        st.markdown("---")

        # --- GRÁFICO ---
        st.subheader("Tendencia de Ventas")
        
        df_chart = df_filtered.groupby('fecha_str').agg(
            Cantidad=('nro_contract', 'count'),
            Monto=('valor_contado', 'sum'),
            FechaReal=('contract_date', 'min')
        ).reset_index().sort_values('FechaReal')

        if not df_chart.empty:
            fig = go.Figure()
            
            # Barras
            fig.add_trace(go.Bar(
                x=df_chart['fecha_str'], 
                y=df_chart['Cantidad'],
                name='Unidades', marker_color='#003366', yaxis='y'
            ))
            
            # Línea
            fig.add_trace(go.Scatter(
                x=df_chart['fecha_str'], 
                y=df_chart['Monto'],
                name='Monto ($)', mode='lines+markers',
                line=dict(color='#D4AF37', width=3), marker=dict(size=6, color='#D4AF37'), yaxis='y2'
            ))

            fig.update_layout(
                template="plotly_white",
                height=400,
                legend=dict(orientation="h", y=1.1, x=0),
                xaxis=dict(
                    type='category',
                    title="",
                    showgrid=False
                ),
                yaxis=dict(
                    title=dict(text="Unidades", font=dict(color="#003366")),
                    tickfont=dict(color="#003366"),
                    showgrid=True, gridcolor='#EEEEEE'
                ),
                yaxis2=dict(
                    title=dict(text="Monto ($)", font=dict(color="#D4AF37")),
                    tickfont=dict(color="#D4AF37"),
                    overlaying="y", side="right", tickformat="$,.0f", showgrid=False
                ),
                margin=dict(l=20, r=20, t=50, b=20),
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")