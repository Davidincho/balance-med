import streamlit as st
import pandas as pd
from datetime import datetime
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
    
    # Selector de modo de análisis
    modo_analisis = st.radio(
        "Modo de análisis:",
        options=["Semana automática", "Rango de fechas personalizado"],
        help="Semana automática: analiza la semana de los archivos subidos\nRango personalizado: elige fechas específicas"
    )
    
    fecha_inicio = None
    fecha_fin = None
    
    if modo_analisis == "Rango de fechas personalizado":
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input(
                "Fecha inicio:",
                value=datetime(2025, 10, 30),
                help="Primer día del análisis"
            )
        with col2:
            fecha_fin = st.date_input(
                "Fecha fin:",
                value=datetime.now(),
                help="Último día del análisis"
            )
        
        # Validar que fecha_fin sea mayor que fecha_inicio
        if fecha_inicio and fecha_fin and fecha_inicio > fecha_fin:
            st.error("⚠️ La fecha de inicio debe ser anterior a la fecha fin")
    
    st.divider()
    
    incluir_fines_semana = st.checkbox(
        "Incluir fines de semana (jornadas extraordinarias)",
        value=True,
        help="Activar para analizar sábados y domingos si hay archivos disponibles"
    )
    
    st.divider()
    st.subheader("📁 Cargar Archivos")
    st.markdown("Sube los archivos CSV de inventario")
    st.caption("Mínimo 3 días requeridos")

# Upload de archivos
archivos_subidos = st.file_uploader(
    "Selecciona archivos CSV de inventario",
    type=['csv'],
    accept_multiple_files=True,
    help="Formato: inventario_YYYY-MM-DD.csv con columnas: codigo, nombre, cantidad"
)

if archivos_subidos:
    st.success(f"✓ {len(archivos_subidos)} archivo(s) cargado(s)")
    
    # Mostrar lista de archivos
    with st.expander("📄 Ver archivos cargados y vista previa"):
        for i, archivo in enumerate(archivos_subidos):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"• {archivo.name}")
            with col2:
                st.caption(f"{archivo.size / 1024:.1f} KB")
            
            # Vista previa del archivo
            if st.checkbox(f"Ver vista previa", key=f"preview_{i}"):
                try:
                    # Intentar leer el archivo con pandas
                    import io
                    archivo.seek(0)
                    contenido = archivo.read().decode('latin-1', errors='ignore')
                    lineas = contenido.split('\n')[:5]
                    
                    st.code('\n'.join(lineas), language='text')
                    st.caption("Primeras 5 líneas del archivo")
                except Exception as e:
                    st.error(f"No se pudo mostrar vista previa: {str(e)}")
    
    # Botón para procesar
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        procesar = st.button("🚀 Analizar Inventario", type="primary", use_container_width=True)
    
    if procesar:
        if len(archivos_subidos) < 3:
            st.error("❌ Se requieren al menos 3 archivos para realizar el análisis")
        else:
            # Crear carpeta temporal para guardar archivos
            temp_dir = tempfile.mkdtemp()
            temp_input = os.path.join(temp_dir, 'inventarios')
            temp_output = os.path.join(temp_dir, 'reportes')
            os.makedirs(temp_input, exist_ok=True)
            os.makedirs(temp_output, exist_ok=True)
            
            try:
                with st.spinner("📂 Guardando archivos..."):
                    # Guardar archivos subidos en carpeta temporal
                    for archivo in archivos_subidos:
                        ruta_archivo = os.path.join(temp_input, archivo.name)
                        with open(ruta_archivo, 'wb') as f:
                            f.write(archivo.getbuffer())
                
                with st.spinner("🔄 Procesando datos..."):
                    # Crear analizador
                    analyzer = InventoryAnalyzer(
                        input_folder=temp_input,
                        output_folder=temp_output,
                        incluir_fines_semana=incluir_fines_semana
                    )
                    
                    # Determinar fecha de inicio según el modo
                    if modo_analisis == "Rango de fechas personalizado":
                        # Usar las fechas seleccionadas por el usuario
                        fecha_inicio_analisis = datetime.combine(fecha_inicio, datetime.min.time())
                        fecha_fin_analisis = datetime.combine(fecha_fin, datetime.min.time())
                        
                        # Calcular el lunes de la semana de fecha_inicio
                        dias_hasta_lunes = fecha_inicio_analisis.weekday()
                        semana_inicio = fecha_inicio_analisis - timedelta(days=dias_hasta_lunes)
                        
                        st.info(f"📅 Analizando desde {fecha_inicio.strftime('%d/%m/%Y')} hasta {fecha_fin.strftime('%d/%m/%Y')}")
                    else:
                        # Modo automático: detecta la semana de los archivos
                        semana_inicio = None
                        fecha_inicio_analisis = None
                        fecha_fin_analisis = None
                    
                    # Ejecutar análisis con rango de fechas personalizado
                    archivo_reporte = analyzer.ejecutar_analisis_completo(
                        semana_inicio=semana_inicio,
                        fecha_inicio_filtro=fecha_inicio_analisis,
                        fecha_fin_filtro=fecha_fin_analisis
                    )
                    
                    # Leer el reporte generado
                    df_reporte = pd.read_excel(archivo_reporte, sheet_name='Reporte Semanal')
                    df_resumen = pd.read_excel(archivo_reporte, sheet_name='Resumen')
                
                st.success("✅ Análisis completado exitosamente")
                
                # MOSTRAR RESULTADOS
                tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Resumen", "🔴 Alertas Críticas", "🔵 Revisar", "📈 Datos Completos", "📋 Log"])
                
                with tab1:
                    st.subheader("📈 Resumen del Análisis")
                    
                    # Extraer métricas del resumen
                    total_productos = int(df_resumen[df_resumen['Métrica'] == 'Total Productos Analizados']['Valor'].values[0])
                    criticas = int(df_resumen[df_resumen['Métrica'] == 'Productos con Alerta Crítica']['Valor'].values[0])
                    medias = int(df_resumen[df_resumen['Métrica'] == 'Productos con Alerta Media']['Valor'].values[0])
                    moderadas = int(df_resumen[df_resumen['Métrica'] == 'Productos con Alerta Moderada']['Valor'].values[0])
                    estables = int(df_resumen[df_resumen['Métrica'] == 'Productos Estables']['Valor'].values[0])
                    revisar = int(df_resumen[df_resumen['Métrica'] == 'Productos a Revisar (Posible Reabastecimiento)']['Valor'].values[0])
                    
                    # Métricas principales
                    col1, col2, col3, col4, col5 = st.columns(5)
                    
                    with col1:
                        st.metric("Total Productos", total_productos)
                    with col2:
                        st.metric("🔴 Críticas", criticas, 
                                delta=f"{(criticas/total_productos*100):.1f}%",
                                delta_color="inverse")
                    with col3:
                        st.metric("🟠 Medias", medias,
                                delta=f"{(medias/total_productos*100):.1f}%")
                    with col4:
                        st.metric("🟢 Estables", estables,
                                delta=f"{(estables/total_productos*100):.1f}%",
                                delta_color="normal")
                    with col5:
                        st.metric("🔵 A Revisar", revisar,
                                delta="Posibles reabastecimientos")
                    
                    st.divider()
                    
                    # Tabla de resumen completo
                    st.subheader("📋 Información Detallada")
                    st.dataframe(df_resumen, use_container_width=True, hide_index=True)
                    
                    st.divider()
                    
                    # Gráfico de distribución de alertas
                    st.subheader("📊 Distribución de Alertas")
                    
                    datos_grafico = pd.DataFrame({
                        'Estado': ['🔴 Crítica', '🟠 Media', '🟡 Moderada', '🟢 Estable', '🔵 Revisar'],
                        'Cantidad': [criticas, medias, moderadas, estables, revisar]
                    })
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.bar_chart(datos_grafico.set_index('Estado'), height=300)
                    with col2:
                        # Mostrar tabla sin gradient (sin matplotlib)
                        st.dataframe(
                            datos_grafico,
                            use_container_width=True,
                            hide_index=True
                        )
                
                with tab2:
                    st.subheader("⚠️ Productos en Estado Crítico")
                    
                    # Filtrar solo críticas
                    df_criticas = df_reporte[df_reporte['Estado'] == '🔴 CRÍTICA'].copy()
                    
                    if len(df_criticas) > 0:
                        st.warning(f"⚠️ {len(df_criticas)} productos requieren atención INMEDIATA")
                        
                        # Mostrar tabla de críticas sin gradient
                        st.dataframe(
                            df_criticas,
                            use_container_width=True,
                            hide_index=True,
                            height=400
                        )
                        
                        # Botón de descarga solo críticas
                        csv_criticas = df_criticas.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Descargar Solo Alertas Críticas (CSV)",
                            data=csv_criticas,
                            file_name=f'alertas_criticas_{datetime.now().strftime("%Y%m%d_%H%M")}.csv',
                            mime='text/csv',
                        )
                    else:
                        st.success("✅ ¡Excelente! No hay productos en estado crítico")
                
                with tab3:
                    st.subheader("📋 Reporte Completo de Inventario")
                    
                    # Filtros
                    col1, col2 = st.columns(2)
                    with col1:
                        filtro_estado = st.multiselect(
                            "Filtrar por estado:",
                            options=df_reporte['Estado'].unique(),
                            default=df_reporte['Estado'].unique()
                        )
                    with col2:
                        buscar_producto = st.text_input("🔍 Buscar producto:", "")
                    
                    # Aplicar filtros
                    df_filtrado = df_reporte[df_reporte['Estado'].isin(filtro_estado)]
                    if buscar_producto:
                        df_filtrado = df_filtrado[
                            df_filtrado['Producto'].str.contains(buscar_producto, case=False, na=False) |
                            df_filtrado['Código'].str.contains(buscar_producto, case=False, na=False)
                        ]
                    
                    st.caption(f"Mostrando {len(df_filtrado)} de {len(df_reporte)} productos")
                    
                    # Mostrar datos
                    st.dataframe(
                        df_filtrado,
                        use_container_width=True,
                        hide_index=True,
                        height=500
                    )
                    
                    # Botones de descarga
                    st.divider()
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Descargar CSV
                        csv = df_filtrado.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Descargar Reporte (CSV)",
                            data=csv,
                            file_name=f'reporte_inventario_{datetime.now().strftime("%Y%m%d_%H%M")}.csv',
                            mime='text/csv',
                            use_container_width=True
                        )
                    
                    with col2:
                        # Descargar Excel original completo
                        with open(archivo_reporte, 'rb') as f:
                            st.download_button(
                                label="📥 Descargar Reporte Completo (Excel)",
                                data=f.read(),
                                file_name=f'reporte_inventario_completo_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
                                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                use_container_width=True
                            )
                
                with tab4:
                    st.subheader("📋 Log del Proceso")
                    
                    # Leer archivo de log
                    log_files = [f for f in os.listdir(temp_output) if f.endswith('.log')]
                    if log_files:
                        with open(os.path.join(temp_output, log_files[0]), 'r', encoding='utf-8') as f:
                            log_content = f.read()
                        
                        st.text_area("Log completo:", log_content, height=400)
                        
                        # Descargar log
                        st.download_button(
                            label="📥 Descargar Log",
                            data=log_content.encode('utf-8'),
                            file_name=f'log_analisis_{datetime.now().strftime("%Y%m%d_%H%M")}.txt',
                            mime='text/plain',
                        )
                    else:
                        st.info("No se encontró archivo de log")
                
            except Exception as e:
                st.error(f"❌ Error durante el análisis:")
                st.exception(e)
            
            finally:
                # Limpiar carpeta temporal
                try:
                    shutil.rmtree(temp_dir)
                except:
                    pass

else:
    # Instrucciones cuando no hay archivos
    st.info("👆 Sube archivos CSV de inventario desde el panel lateral para comenzar")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📝 Formato de Archivos")
        st.code("""
Nombre: inventario_2025-10-06.csv

Contenido (ejemplo):
codigo,nombre,cantidad
MED001,Ibuprofeno 400mg,150
MED002,Acetaminofén 500mg,200
MED003,Losartán 50mg,180
        """, language="csv")
    
    with col2:
        st.markdown("### ✅ Requisitos")
        st.markdown("""
        - **Mínimo:** 3 archivos (3 días diferentes)
        - **Columnas requeridas:**
          - `codigo` o `código`
          - `nombre` o `producto`
          - `cantidad` o `stock`
        - **Separadores aceptados:** `,` `;` `|` o tabulador
        - **Codificación:** UTF-8, Latin-1, Windows-1252
        """)
    
    with st.expander("ℹ️ Instrucciones Detalladas"):
        st.markdown("""
        ### 📚 Cómo usar este sistema:
        
        #### 1️⃣ Prepara tus archivos
        - Asegúrate que tengan las columnas: `codigo`, `nombre`, `cantidad`
        - Nombra los archivos con la fecha: `inventario_YYYY-MM-DD.csv`
        - Ten al menos 3 archivos de días diferentes
        
        #### 2️⃣ Configura opciones
        - En el panel lateral, activa/desactiva "Incluir fines de semana"
        
        #### 3️⃣ Sube archivos
        - Haz clic en "Browse files"
        - Selecciona múltiples archivos (Ctrl/Cmd + clic)
        - O arrastra y suelta los archivos
        
        #### 4️⃣ Analiza
        - Haz clic en "🚀 Analizar Inventario"
        - Espera mientras se procesa (puede tomar unos segundos)
        
        #### 5️⃣ Revisa resultados
        - **Resumen:** Métricas generales y gráficos
        - **Alertas Críticas:** Productos que requieren atención inmediata
        - **Datos Completos:** Tabla completa con filtros y búsqueda
        - **Log:** Detalles técnicos del proceso
        
        #### 6️⃣ Descarga
        - Descarga reportes en CSV o Excel
        - Guarda el log del proceso
        
        ---
        
        ### 🚦 Sistema de Alertas
        
        | Estado | Criterio | Acción |
        |--------|----------|--------|
        | 🔴 **CRÍTICA** | Variación > 20 unidades O stock < 15% | Reabastecer URGENTE |
        | 🟠 **MEDIA** | Variación 10-20 unidades O stock 15-30% | Revisar pronto |
        | 🟡 **MODERADA** | Variación 1-9 unidades | Monitorear |
        | 🟢 **ESTABLE** | Sin variaciones significativas | Todo OK |
        """)

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <small>
        💊 <b>Sistema de Gestión de Inventario</b><br>
        Dispensadora de Medicamentos - Colombia<br>
        Versión 1.0 | 2025
    </small>
</div>
""", unsafe_allow_html=True)
