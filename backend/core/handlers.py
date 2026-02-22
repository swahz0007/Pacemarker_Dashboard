"""
Excel 文件处理器模块
支持 .xls 和 .xlsx 格式
"""

import logging
import xlrd
import openpyxl

# 配置日志
logger = logging.getLogger(__name__)


class XlsHandler:
    """处理旧版 .xls 格式文件"""

    def __init__(self, filepath):
        self.book = xlrd.open_workbook(filepath, formatting_info=True)
        # 智能选择Sheet：优先选择最后一个有数据的Sheet
        # 雅培模板文件中Sheet0是旧模板数据，实际患者数据在Sheet1
        self.sheet = self._select_best_sheet()
        self.nrows = self.sheet.nrows
        self.ncols = self.sheet.ncols

    def _select_best_sheet(self):
        """选择最后一个有数据的Sheet（避免读取模板Sheet）"""
        best_sheet = self.book.sheet_by_index(0)
        for i in range(self.book.nsheets):
            s = self.book.sheet_by_index(i)
            if s.nrows > 0:
                best_sheet = s  # 不断更新为最后一个有数据的sheet
        return best_sheet

    def get_cell_value(self, r, c):
        return self.sheet.cell_value(r, c) if r < self.nrows and c < self.ncols else ""

    def is_blue_cell(self, r, c):
        if r >= self.nrows or c >= self.ncols:
            return False
        try:
            xf_idx = self.sheet.cell_xf_index(r, c)
            return self.book.xf_list[xf_idx].background.pattern_colour_index == 31
        except IndexError:
            return False
        except Exception as e:
            logger.warning(f"检查蓝色单元格失败 ({r},{c}): {e}")
            return False


class XlsxHandler:
    """处理新版 .xlsx 格式文件"""

    def __init__(self, filepath):
        self.wb = openpyxl.load_workbook(filepath, data_only=True)
        self.sheet = self.wb.active
        self.nrows = self.sheet.max_row
        self.ncols = self.sheet.max_column

    def get_cell_value(self, r, c):
        try:
            return self.sheet.cell(row=r + 1, column=c + 1).value
        except IndexError:
            return ""
        except Exception as e:
            logger.warning(f"获取单元格值失败 ({r},{c}): {e}")
            return ""

    def is_blue_cell(self, r, c):
        try:
            cell = self.sheet.cell(row=r + 1, column=c + 1)
            return cell.fill.fgColor.type == "theme" and cell.fill.fgColor.theme == 4
        except AttributeError:
            # 单元格没有 fill 属性
            return False
        except IndexError:
            return False
        except Exception as e:
            logger.warning(f"检查蓝色单元格失败 ({r},{c}): {e}")
            return False


def get_handler(filepath):
    """根据文件扩展名返回对应的处理器"""
    if filepath.lower().endswith(".xls"):
        return XlsHandler(filepath)
    return XlsxHandler(filepath)
