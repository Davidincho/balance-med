import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import glob
import logging
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

class InventoryAnalyzer:
    """
    Sistema de análisis de inventario para dispensadora de medicamentos
    Procesa archivos semanales y genera reportes con alertas automatizadas
    """
    
    def __init__(self, input_folder='./inventarios', output_folder='./reportes', 
                 incluir_fines_semana=True):
        """
        Inicializa el analizador de inventario
        
        Args:
            input_folder: Carpeta donde están los archivos de inventario
            output_folder: Carpeta donde se guardarán los reportes
            incluir_fines_semana: Si True, busca archivos de sábado y domingo también
        """
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.min_dias_validos = 3
        self.incluir_fines_semana = incluir_fines_semana
        
        if incluir_fines_semana:
            self.dias_laborables = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            self.dias_buscar = 7  # Toda la semana
        else:
            self.dias_laborables = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
            self.dias_buscar = 5  # Solo días laborables
        
        # Crear carpetas si no existen
        Path(self.output_folder).mkdir(parents=True, exist_ok=True)
        
        # Configurar logging
        self.setup_logging()
        
    def setup_logging(self):
        """Configura el sistema de logs"""
        log_file = os.path.join(self.output_folder, f'inventario_log_{datetime.now().strftime("%Y%m%d")}.log')
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def cargar_archivos_semana(self, semana_inicio=None, auto_detectar=True):
        """
        Carga los archivos de inventario de la semana
        
        Args:
            semana_inicio: Fecha de inicio de semana (lunes). Si es None, usa la semana actual
            auto_detectar: Si True y no encuentra archivos en semana_inicio, busca la última semana disponible
            
        Returns:
            DataFrame consolidado con todos los días válidos
        """
        if semana_inicio is None:
            hoy = datetime.now()
            # Calcular el lunes de la semana actual
            semana_inicio = hoy - timedelta(days=hoy.weekday())
        
        self.logger.info(f"Iniciando análisis para semana del {semana_inicio.strftime('%Y-%m-%d')}")
        self.logger.info(f"Modo: {'Incluye fines de semana' if self.incluir_fines_semana else 'Solo días laborables'}")
        
        # Primero, listar TODOS los archivos disponibles para diagnóstico
        self.logger.info("="*60)
        self.logger.info("📁 DIAGNÓSTICO: Archivos encontrados en la carpeta")
        self.logger.info("="*60)
        
        todos_archivos = []
        for ext in ['*.xlsx', '*.xls', '*.csv']:
            todos_archivos.extend(glob.glob(os.path.join(self.input_folder, ext)))
        
        if not todos_archivos:
            self.logger.error(f"❌ No se encontraron archivos en: {os.path.abspath(self.input_folder)}")
            self.logger.error(f"   Formatos buscados: .xlsx, .xls, .csv")
            raise FileNotFoundError(f"No hay archivos de inventario en {self.input_folder}")
        
        self.logger.info(f"✓ Total de archivos encontrados: {len(todos_archivos)}")
        for archivo in sorted(todos_archivos):
            self.logger.info(f"  • {os.path.basename(archivo)}")
        
        # Si auto_detectar está activado y no hay archivos de la semana solicitada,
        # buscar la última semana disponible
        if auto_detectar:
            # Extraer fechas de los nombres de archivo
            fechas_disponibles = []
            for archivo in todos_archivos:
                nombre = os.path.basename(archivo)
                # Buscar patrón YYYY-MM-DD
                import re
                match = re.search(r'(\d{4})-(\d{2})-(\d{2})', nombre)
                if match:
                    try:
                        fecha = datetime.strptime(match.group(0), '%Y-%m-%d')
                        fechas_disponibles.append(fecha)
                    except:
                        pass
                # Buscar patrón YYYYMMDD
                match = re.search(r'(\d{8})', nombre)
                if match:
                    try:
                        fecha = datetime.strptime(match.group(0), '%Y%m%d')
                        fechas_disponibles.append(fecha)
                    except:
                        pass
            
            if fechas_disponibles:
                fecha_mas_reciente = max(fechas_disponibles)
                # Calcular el lunes de esa semana
                semana_inicio = fecha_mas_reciente - timedelta(days=fecha_mas_reciente.weekday())
                self.logger.info("="*60)
                self.logger.info(f"🔍 AUTO-DETECCIÓN: Usando semana del {semana_inicio.strftime('%Y-%m-%d')}")
                self.logger.info(f"   (basado en archivo más reciente: {fecha_mas_reciente.strftime('%Y-%m-%d')})")
                self.logger.info("="*60)
        
        # Buscar archivos según configuración
        datos_semanales = []
        dias_faltantes = []
        dias_encontrados = []
        
        for i in range(self.dias_buscar):  # Lunes a Viernes o Lunes a Domingo
            fecha_dia = semana_inicio + timedelta(days=i)
            fecha_str = fecha_dia.strftime('%Y-%m-%d')
            nombre_dia = fecha_dia.strftime('%A')
            es_fin_semana = nombre_dia in ['Saturday', 'Sunday']
            
            # Buscar archivo con diferentes formatos posibles
            patrones = [
                f"inventario_{fecha_str}.*",
                f"inventario_{fecha_dia.strftime('%Y%m%d')}.*",
                f"*{fecha_str}.*",
                f"*{fecha_dia.strftime('%d-%m-%Y')}.*"
            ]
            
            archivo_encontrado = None
            for patron in patrones:
                archivos = glob.glob(os.path.join(self.input_folder, patron))
                if archivos:
                    archivo_encontrado = archivos[0]
                    break
            
            if archivo_encontrado:
                try:
                    df = self.leer_archivo(archivo_encontrado)
                    df['fecha_reporte'] = fecha_dia
                    df['dia_semana'] = nombre_dia
                    df['es_fin_semana'] = es_fin_semana
                    datos_semanales.append(df)
                    dias_encontrados.append(f"{nombre_dia} ({fecha_str})")
                    
                    emoji_dia = "📅" if not es_fin_semana else "🗓️"
                    self.logger.info(f"{emoji_dia} Archivo cargado: {nombre_dia} ({fecha_str}) - {len(df)} productos")
                except Exception as e:
                    self.logger.error(f"✗ Error al leer {archivo_encontrado}: {str(e)}")
                    if not es_fin_semana or self.incluir_fines_semana:
                        dias_faltantes.append(f"{nombre_dia} ({fecha_str})")
            else:
                # Solo reportar como faltante si:
                # 1. Es día laborable (L-V) siempre
                # 2. Es fin de semana Y se configuró para incluirlos
                if not es_fin_semana or self.incluir_fines_semana:
                    dias_faltantes.append(f"{nombre_dia} ({fecha_str})")
                    self.logger.warning(f"✗ No se encontró archivo para {nombre_dia} ({fecha_str})")
                else:
                    self.logger.info(f"⊝ Fin de semana omitido: {nombre_dia} ({fecha_str})")
        
        # Validar días mínimos
        if len(datos_semanales) < self.min_dias_validos:
            self.logger.error("="*60)
            self.logger.error(f"❌ ERROR: Se requieren al menos {self.min_dias_validos} días válidos")
            self.logger.error(f"   Solo se encontraron: {len(datos_semanales)} días")
            self.logger.error(f"   Semana analizada: {semana_inicio.strftime('%Y-%m-%d')} a {(semana_inicio + timedelta(days=6)).strftime('%Y-%m-%d')}")
            self.logger.error("="*60)
            raise ValueError(f"Se requieren al menos {self.min_dias_validos} días válidos. Solo se encontraron {len(datos_semanales)}")
        
        if dias_faltantes:
            self.logger.warning(f"⚠️ Días sin archivo: {', '.join(dias_faltantes)}")
        
        if dias_encontrados:
            self.logger.info(f"✓ Días procesados exitosamente: {', '.join(dias_encontrados)}")
        
        # Consolidar datos
        df_consolidado = pd.concat(datos_semanales, ignore_index=True)
        
        # Contar días normales vs extraordinarios
        dias_normales = len([d for d in datos_semanales if not d['es_fin_semana'].iloc[0]])
        dias_extraordinarios = len([d for d in datos_semanales if d['es_fin_semana'].iloc[0]])
        
        self.logger.info(f"Dataset consolidado: {len(df_consolidado)} registros")
        self.logger.info(f"  - Días laborables (L-V): {dias_normales}")
        if dias_extraordinarios > 0:
            self.logger.info(f"  - Jornadas extraordinarias (S-D): {dias_extraordinarios}")
        
        return df_consolidado, dias_faltantes
    
    def leer_archivo(self, archivo):
        """
        Lee un archivo de inventario (Excel o CSV) con manejo robusto de codificaciones y delimitadores
        
        Args:
            archivo: Ruta del archivo
            
        Returns:
            DataFrame con columnas estandarizadas
        """
        extension = os.path.splitext(archivo)[1].lower()
        
        if extension in ['.xlsx', '.xls']:
            df = pd.read_excel(archivo)
        elif extension == '.csv':
            # Intentar múltiples codificaciones y delimitadores comunes
            codificaciones = ['utf-8-sig', 'latin-1', 'iso-8859-1', 'cp1252', 'windows-1252']
            delimitadores = [',', ';', '|', '\t']  # coma, punto y coma, pipe, tabulador
            df = None
            encoding_exitoso = None
            delimitador_exitoso = None
            
            # Intentar todas las combinaciones de codificación y delimitador
            for encoding in codificaciones:
                if df is not None:
                    break
                for delim in delimitadores:
                    try:
                        df_temp = pd.read_csv(archivo, encoding=encoding, sep=delim)
                        # Verificar que se hayan leído múltiples columnas (no todo en una sola columna)
                        if len(df_temp.columns) > 1:
                            df = df_temp
                            encoding_exitoso = encoding
                            delimitador_exitoso = delim
                            self.logger.debug(f"✓ Archivo leído: encoding={encoding}, delimitador='{delim}'")
                            break
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                    except Exception as e:
                        continue
            
            if df is None:
                # Último intento: usar el sniffer de Python para detectar delimitador
                try:
                    import csv
                    with open(archivo, 'r', encoding='latin-1', errors='ignore') as f:
                        muestra = f.read(4096)
                        sniffer = csv.Sniffer()
                        delim_detectado = sniffer.sniff(muestra).delimiter
                    
                    for encoding in codificaciones:
                        try:
                            df = pd.read_csv(archivo, encoding=encoding, sep=delim_detectado)
                            if len(df.columns) > 1:
                                encoding_exitoso = encoding
                                delimitador_exitoso = delim_detectado
                                self.logger.warning(f"Delimitador auto-detectado: '{delim_detectado}'")
                                break
                        except:
                            continue
                except Exception as e:
                    self.logger.debug(f"No se pudo auto-detectar delimitador: {str(e)}")
            
            if df is None:
                raise ValueError(f"No se pudo leer el archivo. Verifique el formato, codificación y delimitador.")
            
            # Validar que se leyeron datos
            if df.empty or len(df.columns) == 1:
                raise ValueError(f"El archivo parece tener un formato incorrecto. Solo se detectó 1 columna. Delimitador incorrecto?")
                
        else:
            raise ValueError(f"Formato no soportado: {extension}")
        
        # Estandarizar nombres de columnas
        df.columns = df.columns.str.lower().str.strip()
        
        # Mapear columnas a nombres estándar
        mapeo_columnas = {
            'codigo': 'codigo_producto',
            'código': 'codigo_producto',
            'cod': 'codigo_producto',
            'codigo_prod': 'codigo_producto',
            'nombre': 'nombre_producto',
            'producto': 'nombre_producto',
            'descripcion': 'nombre_producto',
            'descripción': 'nombre_producto',
            'cant': 'cantidad',
            'cantidad': 'cantidad',
            'stock': 'cantidad',
            'existencia': 'cantidad'
        }
        
        for col_original, col_nueva in mapeo_columnas.items():
            if col_original in df.columns:
                df.rename(columns={col_original: col_nueva}, inplace=True)
        
        # Validar columnas requeridas
        columnas_requeridas = ['codigo_producto', 'nombre_producto', 'cantidad']
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        
        if columnas_faltantes:
            self.logger.error(f"Columnas disponibles en el archivo: {list(df.columns)}")
            raise ValueError(f"Columnas requeridas no encontradas: {columnas_faltantes}")
        
        # Seleccionar solo columnas necesarias
        df = df[columnas_requeridas].copy()
        
        # Limpiar datos
        df['codigo_producto'] = df['codigo_producto'].astype(str).str.strip()
        df['nombre_producto'] = df['nombre_producto'].astype(str).str.strip()
        df['cantidad'] = pd.to_numeric(df['cantidad'], errors='coerce').fillna(0)
        
        # Eliminar duplicados dentro del mismo archivo
        df = df.drop_duplicates(subset=['codigo_producto'], keep='first')
        
        return df
    
    def calcular_variaciones(self, df_consolidado):
        """
        Calcula la variación semanal de cada producto
        
        Args:
            df_consolidado: DataFrame con todos los días
            
        Returns:
            DataFrame con variaciones calculadas
        """
        # Ordenar por producto y fecha
        df_sorted = df_consolidado.sort_values(['codigo_producto', 'fecha_reporte'])
        
        # Obtener primer y último día para cada producto
        primer_dia = df_sorted.groupby('codigo_producto').first().reset_index()
        ultimo_dia = df_sorted.groupby('codigo_producto').last().reset_index()
        
        # Calcular estadísticas
        df_analisis = pd.DataFrame({
            'codigo_producto': primer_dia['codigo_producto'],
            'nombre_producto': primer_dia['nombre_producto'],
            'cantidad_inicial': primer_dia['cantidad'],
            'cantidad_final': ultimo_dia['cantidad'],
            'fecha_inicial': primer_dia['fecha_reporte'],
            'fecha_final': ultimo_dia['fecha_reporte']
        })
        
        # Calcular variación (consumo = inicial - final)
        df_analisis['variacion_semanal'] = df_analisis['cantidad_inicial'] - df_analisis['cantidad_final']
        
        # Calcular promedio semanal
        promedios = df_consolidado.groupby('codigo_producto')['cantidad'].mean().reset_index()
        promedios.rename(columns={'cantidad': 'promedio_semanal'}, inplace=True)
        df_analisis = df_analisis.merge(promedios, on='codigo_producto', how='left')
        
        # Contar días con registro
        dias_registro = df_consolidado.groupby('codigo_producto').size().reset_index(name='dias_con_registro')
        df_analisis = df_analisis.merge(dias_registro, on='codigo_producto', how='left')
        
        # Excluir productos sin movimiento significativo
        # Excluir si: variación = 0 O solo aparece 1 día
        df_analisis = df_analisis[
            (df_analisis['variacion_semanal'] != 0) | 
            (df_analisis['dias_con_registro'] > 1)
        ].copy()
        
        self.logger.info(f"Productos con movimiento significativo: {len(df_analisis)}")
        
        return df_analisis
    
    def calcular_alertas(self, df_analisis):
        """
        Calcula el indicador de alerta semafórica para cada producto
        
        Args:
            df_analisis: DataFrame con variaciones
            
        Returns:
            DataFrame con columna de alerta
        """
        def clasificar_alerta(row):
            variacion = abs(row['variacion_semanal'])
            stock_final = row['cantidad_final']
            promedio = row['promedio_semanal']
            
            # Calcular porcentaje de stock respecto al promedio
            if promedio > 0:
                porc_stock = (stock_final / promedio) * 100
            else:
                porc_stock = 100
            
            # 🔴 Crítica
            if variacion > 20 or porc_stock < 15:
                return '🔴 CRÍTICA'
            
            # 🟠 Media
            elif (10 <= variacion <= 20) or (15 <= porc_stock < 30):
                return '🟠 MEDIA'
            
            # 🟡 Moderada
            elif 1 <= variacion < 10:
                return '🟡 MODERADA'
            
            # 🟢 Estable
            else:
                return '🟢 ESTABLE'
        
        df_analisis['alerta'] = df_analisis.apply(clasificar_alerta, axis=1)
        
        # Estadísticas de alertas
        conteo_alertas = df_analisis['alerta'].value_counts()
        self.logger.info("Distribución de alertas:")
        for alerta, cantidad in conteo_alertas.items():
            self.logger.info(f"  {alerta}: {cantidad} productos")
        
        return df_analisis
    
    def generar_reporte(self, df_analisis, dias_faltantes):
        """
        Genera el archivo de reporte consolidado
        
        Args:
            df_analisis: DataFrame con el análisis completo
            dias_faltantes: Lista de días sin archivo
            
        Returns:
            Ruta del archivo generado
        """
        # Ordenar por alerta (críticas primero) y variación
        orden_alertas = {'🔴 CRÍTICA': 0, '🟠 MEDIA': 1, '🟡 MODERADA': 2, '🟢 ESTABLE': 3}
        df_analisis['orden_alerta'] = df_analisis['alerta'].map(orden_alertas)
        df_reporte = df_analisis.sort_values(['orden_alerta', 'variacion_semanal'], ascending=[True, False])
        df_reporte = df_reporte.drop('orden_alerta', axis=1)
        
        # Preparar DataFrame para exportación
        df_export = df_reporte[[
            'codigo_producto', 'nombre_producto', 'cantidad_inicial', 'cantidad_final',
            'variacion_semanal', 'promedio_semanal', 'dias_con_registro', 'alerta',
            'fecha_inicial', 'fecha_final'
        ]].copy()
        
        # Renombrar columnas para el reporte
        df_export.columns = [
            'Código', 'Producto', 'Stock Inicial', 'Stock Final',
            'Variación', 'Promedio Semanal', 'Días Registrados', 'Estado',
            'Fecha Inicio', 'Fecha Fin'
        ]
        
        # Generar nombre de archivo
        fecha_reporte = datetime.now().strftime('%Y%m%d_%H%M%S')
        archivo_salida = os.path.join(self.output_folder, f'reporte_inventario_semana_{fecha_reporte}.xlsx')
        
        # Crear Excel con formato
        with pd.ExcelWriter(archivo_salida, engine='openpyxl') as writer:
            # Hoja principal con datos
            df_export.to_excel(writer, sheet_name='Reporte Semanal', index=False)
            
            # Hoja de resumen
            df_resumen = pd.DataFrame({
                'Métrica': [
                    'Fecha de Generación',
                    'Total Productos Analizados',
                    'Productos con Alerta Crítica',
                    'Productos con Alerta Media',
                    'Productos con Alerta Moderada',
                    'Productos Estables',
                    'Días Analizados (Total)',
                    'Días Laborables (L-V)',
                    'Jornadas Extraordinarias (S-D)',
                    'Días Sin Archivo'
                ],
                'Valor': [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    len(df_export),
                    len(df_export[df_export['Estado'] == '🔴 CRÍTICA']),
                    len(df_export[df_export['Estado'] == '🟠 MEDIA']),
                    len(df_export[df_export['Estado'] == '🟡 MODERADA']),
                    len(df_export[df_export['Estado'] == '🟢 ESTABLE']),
                    df_export['Días Registrados'].max(),
                    len([d for d in dias_faltantes if 'Monday' not in d and 'Tuesday' not in d and 
                        'Wednesday' not in d and 'Thursday' not in d and 'Friday' not in d]),
                    df_export['Días Registrados'].max() - len([d for d in dias_faltantes if 
                        'Monday' not in d and 'Tuesday' not in d and 'Wednesday' not in d and 
                        'Thursday' not in d and 'Friday' not in d]),
                    ', '.join(dias_faltantes) if dias_faltantes else 'Ninguno'
                ]
            })
            df_resumen.to_excel(writer, sheet_name='Resumen', index=False)
            
            # Ajustar ancho de columnas
            for sheet_name in writer.sheets:
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column = [cell for cell in column]
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(cell.value)
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column[0].column_letter].width = adjusted_width
        
        self.logger.info(f"Reporte generado exitosamente: {archivo_salida}")
        return archivo_salida, df_export
    
    def ejecutar_analisis_completo(self):
        """
        Ejecuta el proceso completo de análisis y genera el reporte
        
        Returns:
            Ruta del archivo de reporte generado
        """
        try:
            self.logger.info("="*80)
            self.logger.info("INICIO DEL ANÁLISIS SEMANAL DE INVENTARIO")
            self.logger.info("="*80)
            
            # 1. Cargar archivos
            df_consolidado, dias_faltantes = self.cargar_archivos_semana()
            
            # 2. Calcular variaciones
            df_analisis = self.calcular_variaciones(df_consolidado)
            
            # 3. Calcular alertas
            df_analisis = self.calcular_alertas(df_analisis)
            
            # 4. Generar reporte
            archivo_reporte, df_export = self.generar_reporte(df_analisis, dias_faltantes)
            
            # 5. Resumen de alertas críticas
            alertas_criticas = df_export[df_export['Estado'] == '🔴 CRÍTICA']
            if len(alertas_criticas) > 0:
                self.logger.warning(f"⚠️ {len(alertas_criticas)} PRODUCTOS EN ESTADO CRÍTICO")
                self.logger.warning("Revise el reporte para tomar acciones inmediatas")
            
            self.logger.info("="*80)
            self.logger.info("ANÁLISIS COMPLETADO EXITOSAMENTE")
            self.logger.info("="*80)
            
            return archivo_reporte
            
        except Exception as e:
            self.logger.error(f"Error en el análisis: {str(e)}", exc_info=True)
            raise


# ============================================================================
# EJEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    
    # ========================================================================
    # CONFIGURACIÓN DEL ANALIZADOR
    # ========================================================================
    analyzer = InventoryAnalyzer(
        input_folder='./inventarios',      # Carpeta con archivos de entrada
        output_folder='./reportes',        # Carpeta donde se guarda el reporte
        incluir_fines_semana=True          # True: incluye sábados/domingos
                                           # False: solo lunes a viernes
    )
    
    # ========================================================================
    # EJECUTAR ANÁLISIS
    # ========================================================================
    try:
        archivo_generado = analyzer.ejecutar_analisis_completo()
        print(f"\n✓ Proceso completado exitosamente")
        print(f"📊 Reporte generado: {archivo_generado}")
        print(f"📁 Abrir carpeta: {os.path.abspath(analyzer.output_folder)}")
    except Exception as e:
        print(f"\n✗ Error durante el análisis: {str(e)}")
        print(f"📋 Revise el archivo de log para más detalles")