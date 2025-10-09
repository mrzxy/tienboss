#!/usr/bin/env python3
"""
chatting_room_channel.py 的单元测试
"""

import unittest
from chatting_room_channel import extract_stock_symbols


class TestExtractStockSymbols(unittest.TestCase):
    """测试 extract_stock_symbols 函数"""
    
    def test_multiple_symbols_with_content(self):
        """测试多个股票代码加内容"""
        content = "$TSL $SMCI $CJJJ Next stop July Ath $8.37 long"
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, ["$TSL", "$SMCI", "$CJJJ"])
        self.assertEqual(remaining, "Next stop July Ath $8.37 long")
    
    def test_single_symbol_with_content(self):
        """测试单个股票代码加内容"""
        content = "$SMCI Strong Sept"
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, ["$SMCI"])
        self.assertEqual(remaining, "Strong Sept")
    
    def test_only_symbols(self):
        """测试只有股票代码，没有其他内容"""
        content = "$AAPL $TSLA $NVDA - xxxxx"
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, ["$AAPL", "$TSLA", "$NVDA"])
        self.assertEqual(remaining, "- xxxxx")
    
    def test_single_symbol_only(self):
        """测试只有一个股票代码"""
        content = "$AAPL"
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, ["$AAPL"])
        self.assertEqual(remaining, "")
    
    def test_no_symbols(self):
        """测试没有股票代码"""
        content = "This is a regular message without symbols"
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, [])
        self.assertEqual(remaining, "This is a regular message without symbols")
    
    def test_symbol_in_middle(self):
        """测试股票代码在中间（不在开头）"""
        content = "Check out $AAPL today"
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, [])
        self.assertEqual(remaining, "Check out $AAPL today")
    
    def test_empty_string(self):
        """测试空字符串"""
        content = ""
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, [])
        self.assertEqual(remaining, "")
    
    def test_whitespace_only(self):
        """测试只有空白字符"""
        content = "   "
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, [])
        self.assertEqual(remaining, "")
    
    def test_leading_whitespace(self):
        """测试前导空白字符"""
        content = "  $AAPL $TSLA Strong buy"
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, ["$AAPL", "$TSLA"])
        self.assertEqual(remaining, "Strong buy")
    
    def test_trailing_whitespace(self):
        """测试尾部空白字符"""
        content = "$NVDA Great performance  "
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, ["$NVDA"])
        self.assertEqual(remaining, "Great performance")
    
    def test_dollar_in_price(self):
        """测试内容中包含价格（如 $8.37）"""
        content = "$TSLA price target $500 by EOY"
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, ["$TSLA"])
        self.assertEqual(remaining, "price target $500 by EOY")
    
    def test_mixed_case(self):
        """测试混合大小写的股票代码"""
        content = "$aapl $TsLa $NVDA Bullish"
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, ["$aapl", "$TsLa", "$NVDA"])
        self.assertEqual(remaining, "Bullish")
    
    def test_none_input(self):
        """测试 None 输入"""
        content = None
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, [])
        self.assertEqual(remaining, "")
    
    def test_symbols_with_numbers(self):
        """测试包含数字的股票代码"""
        content = "$COIN2 $BTC1 trading high"
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, ["$COIN2", "$BTC1"])
        self.assertEqual(remaining, "trading high")
    
    def test_single_dollar_sign(self):
        """测试单独的 $ 符号"""
        content = "$ This is weird"
        symbols, remaining = extract_stock_symbols(content)
        self.assertEqual(symbols, ["$"])
        self.assertEqual(remaining, "This is weird")


if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2)

