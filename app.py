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
    
    st.subheader("📦 Configuración de Stock Mínimo")
    
    usar_promedio = st.radio(
        "Método de cálculo:",
        options=["Basado en promedio semanal", "Valor fijo global"],
        index=0,
        help="Promedio semanal: más dinámico, se adapta a cada producto\nValor fijo: mismo stock mínimo para todos"
    )
    
    if usar_promedio == "Basado en promedio semanal":
        factor_promedio = st.slider(
            "Factor del promedio semanal:",
            min_value=0.1,
            max_value=2.0,
            value=0.5,
            step=0.1,
            help="0.5 = media semana de demanda\n1.0 = una semana completa\n0.3 = 30% del promedio"
        )
        st.caption(f"Stock mínimo = Promedio Semanal × {factor_promedio}")
        stock_minimo_global = 100  # No se usa pero se pasa
        usar_promedio_semanal = True
    else:
        stock_minimo_global = st.number_input(
            "Stock mínimo (unidades):",
            min_value=1,
            value=100,
            step=10,
            help="Mismo valor para todos los productos"
        )
        factor_promedio = 0.5  # No se usa
        usar_promedio_semanal = False
    
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
                    # Crear analizador con configuración del usuario
                    analyzer = InventoryAnalyzer(
                        input_folder=temp_input,
                        output_folder=temp_output,
                        incluir_fines_semana=incluir_fines_semana,
                        stock_minimo_global=stock_minimo_global,
                        usar_promedio_semanal=usar_promedio_semanal,
                        factor_promedio=factor_promedio
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
                    try:
                        df_reporte = pd.read_excel(archivo_reporte, sheet_name='Reporte Semanal')
                        df_resumen = pd.read_excel(archivo_reporte, sheet_name='Resumen')
                        
                        # Debug: mostrar estructura del resumen
                        if df_resumen.empty:
                            st.warning("⚠️ La hoja de resumen está vacía")
                        else:
                            st.info(f"✓ Resumen cargado: {len(df_resumen)} filas")
                            
                    except Exception as e:
                        st.error(f"Error al leer el archivo Excel: {str(e)}")
                        st.error("Revisa el log para más detalles")
                        raise
                
                st.success("✅ Análisis completado exitosamente")
                
                # MOSTRAR RESULTADOS
                tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Resumen", "🔴 Urgentes", "🔵 Revisar", "📈 Datos Completos", "📋 Log", "🔧 Debug"])
                
                with tab1:
                    st.subheader("📈 Resumen del Análisis")
                    
                    # Extraer métricas del resumen con manejo de errores
                    def obtener_metrica(df_resumen, nombre_metrica, default=0):
                        try:
                            resultado = df_resumen[df_resumen['Métrica'] == nombre_metrica]['Valor'].values
                            if len(resultado) > 0:
                                valor = resultado[0]
                                # Si es string con "unidades", extraer el número
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
                    
                    # Si no hay datos en el resumen, calcular directamente del reporte
                    if total_productos == 0:
                        st.warning("⚠️ No se pudo leer el resumen del Excel. Calculando directamente...")
                        total_productos = len(df_reporte)
                        sin_existencias = len(df_reporte[df_reporte['Estado'] == '🔴 SIN EXISTENCIAS'])
                        bajo_stock = len(df_reporte[df_reporte['Estado'] == '🟠 BAJO STOCK'])
                        en_descenso = len(df_reporte[df_reporte['Estado'] == '🟡 EN DESCENSO'])
                        normales = len(df_reporte[df_reporte['Estado'] == '🟢 NORMAL'])
                        revisar = len(df_reporte[df_reporte['Estado'].str.contains('REVISAR', na=False)])
                        
                        if 'Cantidad a Reabastecer' in df_reporte.columns:
                            total_reabastecer = f"{df_reporte['Cantidad a Reabastecer'].sum():.0f} unidades"
                        else:
                            total_reabastecer = "No disponible"
                    
                    # Métricas principales
                    col1, col2, col3, col4, col5 = st.columns(5)
                    
                    with col1:
                        st.metric("Total Productos", total_productos)
                    with col2:
                        st.metric("🔴 Sin Stock", sin_existencias, 
                                delta="¡Urgente!",
                                delta_color="inverse")
                    with col3:
                        st.metric("🟠 Bajo Stock", bajo_stock,
                                delta="Reabastecer pronto")
                    with col4:
                        st.metric("🟡 En Descenso", en_descenso,
                                delta="Monitorear")
                    with col5:
                        st.metric("🟢 Normales", normales,
                                delta="OK",
                                delta_color="normal")
                    
                    # Segunda fila de métricas
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("🔵 A Revisar", revisar, delta="Posibles reabastecimientos")
                    with col2:
                        st.metric("📦 Total a Reabastecer", total_reabastecer)
                    with col3:
                        config_msg = f"{factor_promedio}x promedio" if usar_promedio_semanal else f"{stock_minimo_global} unidades"
                        st.metric("⚙️ Stock Mínimo", config_msg)
                    
                    st.divider()
                    
                    # Tabla de resumen completo
                    st.subheader("📋 Información Detallada")
                    st.dataframe(df_resumen, use_container_width=True, hide_index=True)
                    
                    st.divider()
                    
                    # Gráfico de distribución de alertas
                    st.subheader("📊 Distribución de Estados")
                    
                    datos_grafico = pd.DataFrame({
                        'Estado': ['🔴 Sin Stock', '🟠 Bajo Stock', '🟡 En Descenso', '🟢 Normal', '🔵 Revisar'],
                        'Cantidad': [sin_existencias, bajo_stock, en_descenso, normales, revisar]
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
                    st.subheader("🔵 Productos para Revisar (Posible Reabastecimiento)")
                    
                    # Filtrar productos con posible reabastecimiento
                    df_revisar = df_reporte[df_reporte['Posible Reabastecimiento'] == True].copy()
                    
                    if len(df_revisar) > 0:
                        st.info(f"ℹ️ {len(df_revisar)} productos con variación negativa (posible reabastecimiento)")
                        st.markdown("""
                        **¿Qué significa esto?**
                        - El stock **aumentó** entre el día inicial y final
                        - Puede indicar que hubo entrada de mercancía
                        - Verifica si corresponde a un reabastecimiento real
                        """)
                        
                        st.dataframe(
                            df_revisar[['Código', 'Producto', 'Stock Inicial', 'Stock Final', 
                                       'Variación', 'Promedio Semanal', 'Estado']],
                            use_container_width=True,
                            hide_index=True,
                            height=400
                        )
                        
                        # Botón de descarga
                        csv_revisar = df_revisar.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Descargar Productos a Revisar (CSV)",
                            data=csv_revisar,
                            file_name=f'productos_revisar_{datetime.now().strftime("%Y%m%d_%H%M")}.csv',
                            mime='text/csv',
                        )
                    else:
                        st.success("✅ No hay productos con posible reabastecimiento en este período")
                
                with tab5:
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
        
        1. **Prepara tus archivos:**
           - Formato: `inventario_YYYY-MM-DD.csv`
           - Columnas requeridas: `codigo`, `nombre`, `cantidad`
           - Mínimo 3 archivos (días diferentes)
        
        2. **Configura el stock mínimo:**
           - **Promedio semanal** (recomendado): se adapta a cada producto
           - **Valor fijo**: mismo stock mínimo para todos
        
        3. **Sube los archivos:**
           - Haz clic en "Browse files" arriba
           - Selecciona múltiples archivos (Ctrl/Cmd + clic)
        
        4. **Analiza:**
           - Haz clic en "Analizar Inventario"
           - Revisa los resultados en las pestañas
        
        5. **Descarga:**
           - Descarga el reporte en CSV o Excel
        
        ### 🚦 Nuevos Estados de Inventario:
        
        | Estado | Criterio | Acción |
        |--------|----------|--------|
        | 🔴 **SIN EXISTENCIAS** | Stock Final = 0 | Reabastecer URGENTE |
        | 🟠 **BAJO STOCK** | Stock Final ≤ Stock Mínimo | Reabastecer pronto |
        | 🟡 **EN DESCENSO** | % Abastecimiento < 30% | Monitorear |
        | 🟢 **NORMAL** | Stock saludable | Sin acción |
        | 🔵 **REVISAR** | Variación negativa | Verificar reabastecimiento |
        
        ### 📦 Cálculo de Stock Mínimo:
        
        **Opción 1: Basado en promedio semanal (recomendado)**
        - Stock Mínimo = Promedio Semanal × Factor
        - Factor 0.5 = media semana de demanda
        - Factor 1.0 = una semana completa
        - Se adapta a cada producto según su rotación
        
        **Opción 2: Valor fijo global**
        - Mismo stock mínimo para todos los productos
        - Útil para inventarios homogéneos
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
