import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io
import os
import tempfile
import shutil

# Importar tu clase InventoryAnalyzer
from script_analisis import InventoryAnalyzer

st.set_page_config(
    page_title="Análisis de Inventario - Dispensadora",
    page_icon="💊",
    layout="wide"
)

st.title("📊 Sistema de Análisis de Inventario")
st.markdown("**Dispensadora de Medicamentos - Colombia**")

# Sidebar para configuración
with st.sidebar:
    st.header("⚙️ Configuración")
    
    modo_analisis = st.radio(
        "Modo de análisis:",
        options=["Semana automática", "Rango de fechas personalizado"],
        help="Semana automática: analiza la semana de los archivos subidos"
    )
    
    fecha_inicio = None
    fecha_fin = None
    
    if modo_analisis == "Rango de fechas personalizado":
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha inicio:", value=datetime(2025, 10, 30))
        with col2:
            fecha_fin = st.date_input("Fecha fin:", value=datetime.now())
        
        if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
            st.error("⚠️ La fecha de inicio debe ser anterior a la fecha fin")
    
    st.divider()
    
    incluir_fines_semana = st.checkbox(
        "Incluir fines de semana",
        value=True,
        help="Activar para analizar sábados y domingos"
    )
    
    st.divider()
    
    st.subheader("📦 Configuración de Stock Mínimo")
    
    usar_promedio = st.radio(
        "Método de cálculo:",
        options=["Basado en consumo diario", "Valor fijo global"],
        index=0
    )
    
    if usar_promedio == "Basado en consumo diario":
        factor_promedio = st.slider(
            "Factor del consumo:",
            min_value=0.1,
            max_value=2.0,
            value=0.5,
            step=0.1,
            help="0.5 = 3.5 días de cobertura"
        )
        st.caption(f"Cobertura: {factor_promedio * 7:.1f} días")
        stock_minimo_global = 100
        usar_promedio_semanal = True
    else:
        stock_minimo_global = st.number_input(
            "Stock mínimo (unidades):",
            min_value=1,
            value=100,
            step=10
        )
        factor_promedio = 0.5
        usar_promedio_semanal = False
    
    st.divider()
    st.subheader("📁 Cargar Archivos")
    st.caption("Mínimo 3 días requeridos")

archivos_subidos = st.file_uploader(
    "Selecciona archivos CSV de inventario",
    type=['csv'],
    accept_multiple_files=True,
    help="Formato: inventario_YYYY-MM-DD.csv"
)

if archivos_subidos:
    st.success(f"✓ {len(archivos_subidos)} archivo(s) cargado(s)")
    
    with st.expander("📄 Ver archivos cargados y vista previa"):
        for i, archivo in enumerate(archivos_subidos):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"• {archivo.name}")
            with col2:
                st.caption(f"{archivo.size / 1024:.1f} KB")
            
            if st.checkbox(f"Ver vista previa", key=f"preview_{i}"):
                try:
                    archivo.seek(0)
                    contenido = archivo.read().decode('latin-1', errors='ignore')
                    lineas = contenido.split('\n')[:5]
                    st.code('\n'.join(lineas), language='text')
                    st.caption("Primeras 5 líneas del archivo")
                except Exception as e:
                    st.error(f"No se pudo mostrar vista previa: {str(e)}")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        procesar = st.button("🚀 Analizar Inventario", type="primary", use_container_width=True)
    
    if procesar:
        if len(archivos_subidos) < 3:
            st.error("❌ Se requieren al menos 3 archivos para realizar el análisis")
        else:
            temp_dir = tempfile.mkdtemp()
            temp_input = os.path.join(temp_dir, 'inventarios')
            temp_output = os.path.join(temp_dir, 'reportes')
            os.makedirs(temp_input, exist_ok=True)
            os.makedirs(temp_output, exist_ok=True)
            
            try:
                with st.spinner("📂 Guardando archivos..."):
                    for archivo in archivos_subidos:
                        ruta_archivo = os.path.join(temp_input, archivo.name)
                        with open(ruta_archivo, 'wb') as f:
                            f.write(archivo.getbuffer())
                
                with st.spinner("🔄 Procesando datos..."):
                    analyzer = InventoryAnalyzer(
                        input_folder=temp_input,
                        output_folder=temp_output,
                        incluir_fines_semana=incluir_fines_semana,
                        stock_minimo_global=stock_minimo_global,
                        usar_promedio_semanal=usar_promedio_semanal,
                        factor_promedio=factor_promedio
                    )
                    
                    if modo_analisis == "Rango de fechas personalizado":
                        fecha_inicio_analisis = datetime.combine(fecha_inicio, datetime.min.time())
                        fecha_fin_analisis = datetime.combine(fecha_fin, datetime.min.time())
                        dias_hasta_lunes = fecha_inicio_analisis.weekday()
                        semana_inicio = fecha_inicio_analisis - timedelta(days=dias_hasta_lunes)
                        st.info(f"📅 Analizando desde {fecha_inicio.strftime('%d/%m/%Y')} hasta {fecha_fin.strftime('%d/%m/%Y')}")
                    else:
                        semana_inicio = None
                        fecha_inicio_analisis = None
                        fecha_fin_analisis = None
                    
                    archivo_reporte = analyzer.ejecutar_analisis_completo(
                        semana_inicio=semana_inicio,
                        fecha_inicio_filtro=fecha_inicio_analisis,
                        fecha_fin_filtro=fecha_fin_analisis
                    )
                    
                    try:
                        df_reporte = pd.read_excel(archivo_reporte, sheet_name='Reporte Semanal')
                        df_resumen = pd.read_excel(archivo_reporte, sheet_name='Resumen')
                    except Exception as e:
                        st.error(f"Error al leer el archivo Excel: {str(e)}")
                        raise
                
                st.success("✅ Análisis completado exitosamente")
                
                def obtener_metrica(df_resumen, nombre_metrica, default=0):
                    try:
                        resultado = df_resumen[df_resumen['Métrica'] == nombre_metrica]['Valor'].values
                        if len(resultado) > 0:
                            valor = resultado[0]
                            if isinstance(valor, str) and 'unidades' in valor:
                                return valor.split()[0]
                            return int(valor) if not isinstance(valor, str) else valor
                        return default
                    except:
                        return default
                
                total_productos = obtener_metrica(df_resumen, 'Total Productos Analizados', 0)
                sin_existencias = obtener_metrica(df_resumen, 'Productos Sin Existencias', 0)
                bajo_stock = obtener_metrica(df_resumen, 'Productos con Bajo Stock', 0)
                en_descenso = obtener_metrica(df_resumen, 'Productos En Descenso', 0)
                normales = obtener_metrica(df_resumen, 'Productos Normales', 0)
                revisar = obtener_metrica(df_resumen, 'Productos a Revisar (Posible Reabastecimiento)', 0)
                total_reabastecer = obtener_metrica(df_resumen, 'Total Unidades a Reabastecer', '0 unidades')
                
                if total_productos == 0:
                    st.warning("⚠️ Calculando métricas directamente del reporte...")
                    total_productos = len(df_reporte)
                    sin_existencias = len(df_reporte[df_reporte['Estado'] == '🔴 SIN EXISTENCIAS'])
                    bajo_stock = len(df_reporte[df_reporte['Estado'] == '🟠 BAJO STOCK'])
                    en_descenso = len(df_reporte[df_reporte['Estado'] == '🟡 EN DESCENSO'])
                    normales = len(df_reporte[df_reporte['Estado'] == '🟢 NORMAL'])
                    revisar = len(df_reporte[df_reporte['Estado'].str.contains('REVISAR', na=False)])
                    if 'Cantidad a Reabastecer' in df_reporte.columns:
                        total_reabastecer = f"{df_reporte['Cantidad a Reabastecer'].sum():.0f} unidades"
                
                tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                    "📊 Resumen", "🔴 Urgentes", "🔵 Revisar", 
                    "📈 Datos Completos", "📋 Log", "🔧 Debug"
                ])
                
                with tab1:
                    st.subheader("📈 Resumen del Análisis")
                    
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.metric("Total Productos", total_productos)
                    with col2:
                        st.metric("🔴 Sin Stock", sin_existencias, delta="¡Urgente!", delta_color="inverse")
                    with col3:
                        st.metric("🟠 Bajo Stock", bajo_stock, delta="Reabastecer")
                    with col4:
                        st.metric("🟡 En Descenso", en_descenso, delta="Monitorear")
                    with col5:
                        st.metric("🟢 Normales", normales, delta="OK", delta_color="normal")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("🔵 A Revisar", revisar, delta="Posibles reabastecimientos")
                    with col2:
                        st.metric("📦 Total a Reabastecer", total_reabastecer)
                    with col3:
                        config_msg = f"{factor_promedio}x consumo" if usar_promedio_semanal else f"{stock_minimo_global} und"
                        st.metric("⚙️ Stock Mínimo", config_msg)
                    
                    st.divider()
                    st.subheader("📋 Información Detallada")
                    st.dataframe(df_resumen, use_container_width=True, hide_index=True)
                    
                    st.divider()
                    st.subheader("📊 Distribución de Estados")
                    
                    datos_grafico = pd.DataFrame({
                        'Estado': ['🔴 Sin Stock', '🟠 Bajo Stock', '🟡 En Descenso', '🟢 Normal', '🔵 Revisar'],
                        'Cantidad': [sin_existencias, bajo_stock, en_descenso, normales, revisar]
                    })
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.bar_chart(datos_grafico.set_index('Estado'), height=300)
                    with col2:
                        st.dataframe(datos_grafico, use_container_width=True, hide_index=True)
                
                with tab2:
                    st.subheader("🔴🟠 Productos Urgentes")
                    
                    try:
                        df_urgentes = df_reporte[
                            (df_reporte['Estado'] == '🔴 SIN EXISTENCIAS') | 
                            (df_reporte['Estado'] == '🟠 BAJO STOCK')
                        ].copy()
                    except:
                        df_urgentes = df_reporte[
                            df_reporte['Estado'].str.contains('SIN EXISTENCIAS|BAJO STOCK', case=False, na=False)
                        ].copy()
                    
                    if len(df_urgentes) > 0:
                        st.error(f"⚠️ {len(df_urgentes)} productos requieren atención INMEDIATA")
                        
                        if 'Cantidad a Reabastecer' in df_urgentes.columns:
                            total_unidades = df_urgentes['Cantidad a Reabastecer'].sum()
                            st.metric("📦 Total unidades a reabastecer:", f"{total_unidades:.0f}")
                        
                        columnas_mostrar = ['Código', 'Producto', 'Stock Final', 'Estado']
                        if 'Stock Mínimo' in df_urgentes.columns:
                            columnas_mostrar.insert(3, 'Stock Mínimo')
                        if 'Cantidad a Reabastecer' in df_urgentes.columns:
                            columnas_mostrar.insert(4, 'Cantidad a Reabastecer')
                        
                        st.dataframe(df_urgentes[columnas_mostrar], use_container_width=True, hide_index=True, height=400)
                        
                        csv_urgentes = df_urgentes.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Descargar Productos Urgentes (CSV)",
                            data=csv_urgentes,
                            file_name=f'productos_urgentes_{datetime.now().strftime("%Y%m%d_%H%M")}.csv',
                            mime='text/csv',
                        )
                    else:
                        st.success("✅ ¡Excelente! No hay productos en estado urgente")
                
                with tab3:
                    st.subheader("🔵 Productos para Revisar")
                    
                    df_revisar = df_reporte[df_reporte['Posible Reabastecimiento'] == True].copy()
                    
                    if len(df_revisar) > 0:
                        st.info(f"ℹ️ {len(df_revisar)} productos con posible reabastecimiento")
                        st.markdown("**¿Qué significa?** El stock aumentó - verificar si hubo entrada de mercancía")
                        
                        st.dataframe(df_revisar, use_container_width=True, hide_index=True, height=400)
                        
                        csv_revisar = df_revisar.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Descargar Productos a Revisar (CSV)",
                            data=csv_revisar,
                            file_name=f'productos_revisar_{datetime.now().strftime("%Y%m%d_%H%M")}.csv',
                            mime='text/csv',
                        )
                    else:
                        st.success("✅ No hay productos con posible reabastecimiento")
                
                with tab4:
                    st.subheader("📋 Reporte Completo de Inventario")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        filtro_estado = st.multiselect(
                            "Filtrar por estado:",
                            options=df_reporte['Estado'].unique(),
                            default=df_reporte['Estado'].unique()
                        )
                    with col2:
                        buscar_producto = st.text_input("🔍 Buscar producto:", "")
                    
                    df_filtrado = df_reporte[df_reporte['Estado'].isin(filtro_estado)]
                    if buscar_producto:
                        df_filtrado = df_filtrado[
                            df_filtrado['Producto'].str.contains(buscar_producto, case=False, na=False) |
                            df_filtrado['Código'].str.contains(buscar_producto, case=False, na=False)
                        ]
                    
                    st.caption(f"Mostrando {len(df_filtrado)} de {len(df_reporte)} productos")
                    st.dataframe(df_filtrado, use_container_width=True, hide_index=True, height=500)
                    
                    st.divider()
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        csv = df_filtrado.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Descargar Reporte (CSV)",
                            data=csv,
                            file_name=f'reporte_inventario_{datetime.now().strftime("%Y%m%d_%H%M")}.csv',
                            mime='text/csv',
                            use_container_width=True
                        )
                    
                    with col2:
                        with open(archivo_reporte, 'rb') as f:
                            st.download_button(
                                label="📥 Descargar Reporte Completo (Excel)",
                                data=f.read(),
                                file_name=f'reporte_completo_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
                                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                use_container_width=True
                            )
                
                with tab5:
                    st.subheader("📋 Log del Proceso")
                    
                    log_files = [f for f in os.listdir(temp_output) if f.endswith('.log')]
                    if log_files:
                        with open(os.path.join(temp_output, log_files[0]), 'r', encoding='utf-8') as f:
                            log_content = f.read()
                        
                        st.text_area("Log completo:", log_content, height=400)
                        
                        st.download_button(
                            label="📥 Descargar Log",
                            data=log_content.encode('utf-8'),
                            file_name=f'log_analisis_{datetime.now().strftime("%Y%m%d_%H%M")}.txt',
                            mime='text/plain',
                        )
                    else:
                        st.info("No se encontró archivo de log")
                
                with tab6:
                    st.subheader("🔧 Información de Debug")
                    
                    st.markdown("### 📋 Estructura del Resumen")
                    st.dataframe(df_resumen, use_container_width=True)
                    
                    st.markdown("### 📊 Estados en el Reporte")
                    if 'Estado' in df_reporte.columns:
                        estados_unicos = df_reporte['Estado'].value_counts()
                        st.dataframe(estados_unicos, use_container_width=True)
                    else:
                        st.error("La columna 'Estado' no existe en el reporte")
                    
                    st.markdown("### 📁 Columnas del Reporte")
                    st.write(list(df_reporte.columns))
                    
                    st.markdown("### 🔢 Valores de Variables")
                    st.json({
                        "total_productos": int(total_productos) if isinstance(total_productos, (int, float)) else str(total_productos),
                        "sin_existencias": int(sin_existencias) if isinstance(sin_existencias, (int, float)) else str(sin_existencias),
                        "bajo_stock": int(bajo_stock) if isinstance(bajo_stock, (int, float)) else str(bajo_stock),
                        "en_descenso": int(en_descenso) if isinstance(en_descenso, (int, float)) else str(en_descenso),
                        "normales": int(normales) if isinstance(normales, (int, float)) else str(normales),
                        "revisar": int(revisar) if isinstance(revisar, (int, float)) else str(revisar),
                        "total_reabastecer": str(total_reabastecer)
                    })
            
            except Exception as e:
                st.error(f"❌ Error durante el análisis:")
                st.exception(e)
                
                with st.expander("Ver detalles técnicos del error"):
                    import traceback
                    st.code(traceback.format_exc())
            
            finally:
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass

else:
    st.info("👆 Sube archivos CSV de inventario desde el panel lateral para comenzar")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📝 Formato de Archivos")
        st.code("""Nombre: inventario_2025-10-06.csv

Contenido:
codigo;nombre;cantidad
MED001;Ibuprofeno 400mg;150
MED002;Acetaminofén 500mg;200""", language="csv")
    
    with col2:
        st.markdown("### ✅ Requisitos")
        st.markdown("""
        - **Mínimo:** 3 archivos
        - **Columnas:** codigo, nombre, cantidad
        - **Separadores:** `,` `;` `|` o tabulador
        """)
    
    with st.expander("ℹ️ Instrucciones Detalladas"):
        st.markdown("""
        ### 🚦 Estados de Inventario:
        
        | Estado | Criterio | Acción |
        |--------|----------|--------|
        | 🔴 **SIN EXISTENCIAS** | Stock = 0 | Urgente |
        | 🟠 **BAJO STOCK** | Stock ≤ Mínimo | Reabastecer pronto |
        | 🟡 **EN DESCENSO** | % < 30% | Monitorear |
        | 🟢 **NORMAL** | Stock OK | Sin acción |
        | 🔵 **REVISAR** | Variación negativa | Verificar |
        """)

st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <small>💊 Sistema de Gestión de Inventario - Dispensadora Colombia | v2.0 | 2025</small>
</div>
""", unsafe_allow_html=True)
