import clang.cindex
import subprocess
import re

_cpp_include_args = None

def get_cpp_include_args():
    global _cpp_include_args
    if _cpp_include_args is not None:
        return _cpp_include_args
        
    try:
        out = subprocess.run(['g++', '-E', '-v', '-x', 'c++', '-'], input=b'', capture_output=True, text=True).stderr
        paths = re.findall(r'#include <...> search starts here:\n(.*?)\nEnd of search list.', out, re.DOTALL)
        args = []
        if paths:
            for p in paths[0].strip().split('\n'):
                args.append('-I' + p.strip())
        _cpp_include_args = args
    except Exception:
        _cpp_include_args = []
        
    return _cpp_include_args
import os

def get_cpp_template():
    return r"""
#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <sstream>
#include <map>

std::ofstream __trace_file;
bool __trace_init = false;

std::string __escape_json(const std::string& s) {
    std::string res;
    for (char c : s) {
        if (c == '"') res += "\\\"";
        else if (c == '\\') res += "\\\\";
        else if (c == '\n') res += "\\n";
        else if (c == '\r') res += "\\r";
        else if (c == '\t') res += "\\t";
        else res += c;
    }
    return res;
}

template <typename T>
std::string __to_json(const T& val, std::string type = "prim") {
    std::ostringstream oss;
    oss << val;
    return "{\"type\": \"" + type + "\", \"val\": \"" + __escape_json(oss.str()) + "\"}";
}

template <>
std::string __to_json<std::string>(const std::string& val, std::string type) {
    return "{\"type\": \"prim\", \"val\": \"'" + __escape_json(val) + "'\"}";
}

template <>
std::string __to_json<char>(const char& val, std::string type) {
    std::string s(1, val);
    return "{\"type\": \"prim\", \"val\": \"'" + __escape_json(s) + "'\"}";
}

template <typename T>
std::string __to_json(const std::vector<T>& val, std::string type = "list") {
    std::string res = "{\"type\": \"list\", \"val\": [";
    for (size_t i = 0; i < val.size(); ++i) {
        std::ostringstream oss;
        oss << val[i];
        res += "\"" + __escape_json(oss.str()) + "\"";
        if (i < val.size() - 1) res += ", ";
    }
    res += "]}";
    return res;
}

template <typename T, size_t N>
std::string __to_json(const T (&val)[N], std::string type = "list") {
    std::string res = "{\"type\": \"list\", \"val\": [";
    for (size_t i = 0; i < N; ++i) {
        std::ostringstream oss;
        oss << val[i];
        res += "\"" + __escape_json(oss.str()) + "\"";
        if (i < N - 1) res += ", ";
    }
    res += "]}";
    return res;
}

void __dump_state(int line, std::string func_name, const std::map<std::string, std::string>& vars) {
    if (!__trace_init) {
        __trace_file.open("trace.json");
        __trace_file << "[\n";
        __trace_init = true;
    } else {
        __trace_file << ",\n";
    }
    
    __trace_file << "  {\"line\": " << line << ", \"func_name\": \"" << func_name << "\", \"vars\": {";
    bool first = true;
    for (auto const& pair : vars) {
        if (!first) __trace_file << ", ";
        __trace_file << "\"" << pair.first << "\": " << pair.second;
        first = false;
    }
    __trace_file << "}}";
}

struct __TraceCloser {
    ~__TraceCloser() {
        if (__trace_init) {
            __trace_file << "\n]\n";
            __trace_file.close();
        }
    }
} __trace_closer_inst;

"""

class Instrumenter:
    def __init__(self, code):
        self.code = code
        self.index = clang.cindex.Index.create()
        self.tu = self.index.parse(
            'temp_source.cpp', 
            args=['-std=c++17'] + get_cpp_include_args(), 
            unsaved_files=[
                ('temp_source.cpp', self.code),
                ('bits/stdc++.h', '#include <iostream>\n#include <vector>\n#include <string>\n#include <map>\n#include <set>\n#include <algorithm>\n#include <cmath>\n')
            ]
        )
        self.insertions = [] # list of (offset, string_to_insert)
        self.scopes = [] # Stack of list of var_names
        self.global_vars = []
        
    def get_all_vars_in_scope(self):
        vars_in_scope = []
        for scope in self.scopes:
            vars_in_scope.extend(scope)
        return vars_in_scope
        
    def generate_dump_code(self, line_num, func_name):
        vars_in_scope = self.get_all_vars_in_scope()
        dump_code = f" {{ std::map<std::string, std::string> __v; "
        for v in vars_in_scope:
            dump_code += f"__v[\"{v}\"] = __to_json({v}); "
        for v in self.global_vars:
            dump_code += f"__v[\"[Global] {v}\"] = __to_json({v}); "
        dump_code += f"__dump_state({line_num}, \"{func_name}\", __v); }}"
        return dump_code

    def find_next_semicolon(self, offset):
        while offset < len(self.code) and self.code[offset] != ';':
            offset += 1
        return offset

    def traverse(self, node, current_func_name="main"):
        if node.location.file and node.location.file.name != 'temp_source.cpp':
            return
            
        if node.kind == clang.cindex.CursorKind.VAR_DECL and node.lexical_parent and node.lexical_parent.kind == clang.cindex.CursorKind.TRANSLATION_UNIT:
            type_spelling = node.type.spelling
            if any(t in type_spelling for t in ['int', 'float', 'double', 'char', 'string', 'bool', 'long', 'short', 'vector']):
                self.global_vars.append(node.spelling)
            
        if node.kind == clang.cindex.CursorKind.FUNCTION_DECL:
            current_func_name = node.spelling
            
        if node.kind == clang.cindex.CursorKind.COMPOUND_STMT:
            self.scopes.append([])
            children = list(node.get_children())
            
            if children:
                first = children[0]
                offset = first.extent.start.offset
                line_num = first.extent.start.line
                dump_code = self.generate_dump_code(line_num, current_func_name)
                self.insertions.append((offset, dump_code + " "))
                
            for i, child in enumerate(children):
                self.traverse(child, current_func_name)
                
                if child.kind == clang.cindex.CursorKind.DECL_STMT:
                    for decl in child.get_children():
                        if decl.kind == clang.cindex.CursorKind.VAR_DECL:
                            type_spelling = decl.type.spelling
                            if any(t in type_spelling for t in ['int', 'float', 'double', 'char', 'string', 'bool', 'long', 'short', 'vector']):
                                self.scopes[-1].append(decl.spelling)
                                
                if child.kind == clang.cindex.CursorKind.RETURN_STMT:
                    continue
                    
                if i + 1 < len(children):
                    next_line = children[i+1].extent.start.line
                else:
                    next_line = child.extent.end.line + 1
                    
                offset = child.extent.end.offset
                temp_offset = offset
                while temp_offset < len(self.code) and self.code[temp_offset].isspace():
                    temp_offset += 1
                if temp_offset < len(self.code) and self.code[temp_offset] == ';':
                    offset = temp_offset + 1
                    
                dump_code = self.generate_dump_code(next_line, current_func_name)
                self.insertions.append((offset, dump_code))

            self.scopes.pop()
        else:
            if node.kind in [clang.cindex.CursorKind.FOR_STMT, clang.cindex.CursorKind.WHILE_STMT, clang.cindex.CursorKind.CXX_FOR_RANGE_STMT]:
                children = list(node.get_children())
                if children:
                    body = children[-1]
                    if body.kind != clang.cindex.CursorKind.COMPOUND_STMT:
                        offset_start = body.extent.start.offset
                        offset_end = body.extent.end.offset
                        temp_offset = offset_end
                        while temp_offset < len(self.code) and self.code[temp_offset].isspace():
                            temp_offset += 1
                        if temp_offset < len(self.code) and self.code[temp_offset] == ';':
                            offset_end = temp_offset + 1
                        
                        next_line = body.extent.end.line + 1
                        dump_code = self.generate_dump_code(next_line, current_func_name)
                        
                        self.insertions.append((offset_end, "} " + dump_code))
                        self.insertions.append((offset_start, "{ "))
                        
            for child in node.get_children():
                self.traverse(child, current_func_name)

    def instrument(self):
        self.traverse(self.tu.cursor)
        
        # Sort insertions in reverse order to not mess up offsets
        self.insertions.sort(key=lambda x: x[0], reverse=True)
        
        result = self.code
        for offset, dump_code in self.insertions:
            result = result[:offset] + dump_code + result[offset:]
            
        return get_cpp_template() + "\n" + result

def instrument_cpp_code(code):
    inst = Instrumenter(code)
    return inst.instrument()

if __name__ == "__main__":
    sample_code = """
#include <bits/stdc++.h>
using namespace std;
int main() { int a=5; int b=10; int c=a+b; cout<<c<<endl; if(a>0){int d=a*2; cout<<d<<endl;} return 0; }
"""
    print(instrument_cpp_code(sample_code))
