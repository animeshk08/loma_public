import codegen_c
import ir
ir.generate_asdl_file()
import _asdl.loma as loma_ir
import compiler

class OpenCLCodegenVisitor(codegen_c.CCodegenVisitor):
    """ Generates OpenCL code from loma IR.
    """

    def __init__(self, func_defs):
        super().__init__(func_defs)

    def visit_function_def(self, node):
        if node.is_simd:
            self.code += f'__kernel void {node.id}('
            for i, arg in enumerate(node.args):
                if i > 0:
                    self.code += ', '
                self.code += f'__global {codegen_c.type_to_string(arg)} {arg.id}'
            self.code += ') {\n'
        else:
            self.code += f'{codegen_c.type_to_string(node.ret_type)} {node.id}('
            for i, arg in enumerate(node.args):
                if i > 0:
                    self.code += ', '
                self.code += f'{codegen_c.type_to_string(arg)} {arg.id}'
            self.code += ') {\n'

        self.byref_args = set([arg.id for arg in node.args if \
            arg.i == loma_ir.Out() and (not isinstance(arg.t, loma_ir.Array))])

        self.tab_count += 1
        for stmt in node.body:
            self.visit_stmt(stmt)

        self.tab_count -= 1
        self.emit_tabs()
        self.code += '}\n'

    def visit_expr(self, expr):
        match expr:
            case loma_ir.Call():
                if expr.id == 'thread_id':
                    return 'get_global_id(0)'
                else:
                    return super().visit_expr(expr)
            case _:
                return super().visit_expr(expr)



def codegen_opencl(structs : dict[str, loma_ir.Struct],
                   funcs : dict[str, loma_ir.func]) -> str:
    """ Given loma Structs (structs) and loma functions (funcs),
        return a string that represents the equivalent OpenCL code.

        Parameters:
        structs - a dictionary that maps the ID of a Struct to 
                the corresponding Struct
        funcs - a dictionary that maps the ID of a function to 
                the corresponding func
    """

    sorted_structs_list = compiler.topo_sort_structs(structs)

    # Definition of structs
    code = ''
    for s in sorted_structs_list:
        code += f'typedef struct {s.id} {{\n'
        for m in s.members:
            code += f'\t{codegen_c.type_to_string(m.t)} {m.id};\n'
        code += f'}} {s.id};\n'

    # Forward declaration of functions
    for f in funcs.values():
        if f.is_simd:
            code += '__kernel '
        code += f'{codegen_c.type_to_string(f.ret_type)} {f.id}('
        for i, arg in enumerate(f.args):
            if i > 0:
                code += ', '
            if f.is_simd:
                code += '__global '
            code += f'{codegen_c.type_to_string(arg)}'
            code += f' {arg.id}'
        code += ');\n'

    for f in funcs.values():
        cg = OpenCLCodegenVisitor(funcs)
        cg.visit_function(f)
        code += cg.code

    return code
