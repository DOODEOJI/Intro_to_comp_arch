import sys
import re

INSTRUCTION_MEMORY_START = 0x00000000
INSTRUCTION_MEMORY_SIZE = 64 * 1024

MEMORY_START = 0x10000000
MEMORY_SIZE = 64 * 1024
S_MEMORY_START = 0x20000000

instruction_memory = bytearray([0x0]*INSTRUCTION_MEMORY_SIZE)
data_memory = bytearray([0xFF]*MEMORY_SIZE)

s_data_memory = bytearray([0xFF] * 4)

register_list = []  

class Register:
    def __init__(self, name, value=0):
        self.name = name
        self._value = value & 0xFFFFFFFF

    @property
    def value(self):
        if self.name == "x0":
            return 0
        return self._value
    
    @value.setter
    def value(self, value):
        if self.name == "x0":
            return
        self._value = value

    def __str__(self):
        return f"{self.name}: 0x{self.value:08x}"
        
    def add(self, other):
        if isinstance(other, Register):
            return (self.value + other.value) & 0xFFFFFFFF
        else:
            return (self.value + other) & 0xFFFFFFFF

    def sub(self, other):
        if isinstance(other, Register):
            return (self.value - other.value) & 0xFFFFFFFF
        else:
            return (self.value - other) & 0xFFFFFFFF

    def lshift(self, other):
        if isinstance(other, Register):
            return (self.value << (other.value & 0x1F)) & 0xFFFFFFFF
        return (self.value << other) & 0xFFFFFFFF

    def rashift(self, other):
        if isinstance(other, Register):
            if (format(self.value, '032b'))[0] == '1':
                one_mask = ((2**(other.value & 0x1F)) -1) << (32 - (other.value & 0x1F))
                return ((self.value >> (other.value & 0x1F)) | one_mask) & 0xFFFFFFFF 
            else:
                return (self.value >> (other.value & 0x1F)) & 0xFFFFFFFF
        else:
            if (format(self.value, '032b'))[0] == '1':
                one_mask = ((2**other)-1) << (32-other)
                return ((self.value >> other) | one_mask) & 0xFFFFFFFF 
            else:
                return (self.value >> other) & 0xFFFFFFFF 

    def rlshift(self, other):
        if isinstance(other, Register):
            return self.value >> (other.value & 0x1F)
        return self.value >> other
    
    def slt(self, other):
        if isinstance(other, Register):
            return 1 if twosint(self.value) < twosint(other.value) else 0
        return 1 if twosint(self.value) < twosint(other) else 0
    
    def xor(self, other):
        if isinstance(other, Register):
            return (self.value ^ other.value) & 0xFFFFFFFF
        return (self.value ^ other) & 0xFFFFFFFF
    
    def myor(self, other):
        if isinstance(other, Register):
            return (self.value | other.value) & 0xFFFFFFFF
        return (self.value | other) & 0xFFFFFFFF
    
    def myand(self, other):
        if isinstance(other, Register):
            return self.value & other.value & 0xFFFFFFFF
        return self.value & other & 0xFFFFFFFF
    
    def beq(self, other):
        return 1 if self.value == other.value else 0
    
    def bne(self, other):
        return 1 if self.value != other.value else 0
    
    def blt(self, other):
        return 1 if twosint(format(self.value, '032b')) < twosint(format(other.value, '032b')) else 0
    
    def bge(self, other):
        return 1 if twosint(format(self.value, '032b')) >= twosint(format(other.value, '032b')) else 0
    
    def lw(self, other):
        address = int(self.value) + other
        
        if address == S_MEMORY_START:
            input_value = input()
            return twosint(format(int(input_value), '032b')) & 0xFFFFFFFF

        else:
            offset = address - MEMORY_START
            data = data_memory[offset:offset+4]
            value = int.from_bytes(data, byteorder='big')
            value = twosint(format(value, '032b')) & 0xFFFFFFFF
            return value

    def sw(self, rs2, immediate):
        if (int(self.value) + twosint(immediate)) == S_MEMORY_START:
            s_data_memory[0:4] = (rs2.value & 0xFFFFFFFF).to_bytes(4, byteorder='big')
            print(chr(s_data_memory[3]), end='')
        else:
            address = int(self.value) + twosint(immediate)
            offset = address - MEMORY_START
            data_memory[offset:offset+4] = rs2.value.to_bytes(4, byteorder='big')
        #print_memory()
        #print(f"[sw] address   : {address} (0x{address:X}), offset: {offset}, mem size: {len(data_memory)}")

def init_registers():
    register_list.clear()
    for i in range(32):
        register_list.append(Register(f"x{i}"))

def print_registers():
    for register in register_list:
        print(register)
    
def read_binary_txt(filename, memory):
    inst_count = 0
    with open(filename, "rb") as file:
        data = file.read()

    for i in range(0, len(data), 4):
        chunk = data[i:i+4]
        inst_count += 4
        for j in range(4):
            memory[i + j] = chunk[3 - j]
    return inst_count

def twosint(num):
    if isinstance(num, int):
        num = format(num, '032b')

    if num[0] == '1':
        return -2**(len(num)-1)+int(num[1:],2)
    else:
        return int(num,2)

def make_register_name(register, last = 0):
    decimal = int(register,2)
    if last:
         return "x" + str(decimal)
    return "x" + str(decimal) +", "        

class CPU:
    def __init__(self):
        self.pc = 0x00000000

    def fetch(self):
        offset = self.pc - INSTRUCTION_MEMORY_START
        instruction = instruction_memory[offset:offset+4]
        instruction = format(int.from_bytes(instruction, byteorder='big'),'032b')
        return instruction
    
    def decode(self, instruction):
        opcode_map = {
            "0110111": self.Utype,
            "0010111": self.Utype,
            "0010011": {"001": self.Rtype, "101": self.Rtype}, # 이외의 opcode는 rtype으로 처리
            "0110011": self.Rtype,
            "0000011": self.Itype,
            "1100111": self.Itype,
            "0100011": self.Stype,
            "1100011": self.Btype,
            "1101111": self.Jtype
        }

        opcode = instruction[25:32]

        if opcode not in opcode_map:
            print("unknown instruction")

        if isinstance(opcode_map[opcode], dict):
            funct3 = instruction[17:20]
            if funct3 in opcode_map[opcode]:
                opcode_map[opcode][funct3](opcode, instruction)
            else:
                self.Itype(opcode, instruction)
        else:
            opcode_map[opcode](opcode, instruction)

    def Rtype(self, opcode, instruction):
        
        rtype_map = {
            "000": {"0000000": ("add", Register.add), "0100000": ("sub", Register.sub)},
            "001": ("sll", Register.lshift),
            "010": ("slt", Register.slt),
            "011": "sltu",
            "100": ("xor", Register.xor),
            "101": {"0000000": ("srl", Register.rlshift), "0100000": ("sra", Register.rashift),},
            "110": ("or", Register.myor),
            "111": ("and", Register.myand),
        }

        funct3 = instruction[17:20]
        funct7 = instruction[0:7]

        rs1 = make_register_name(instruction[12:17])
        rs2 = make_register_name(instruction[7:12],1)
        rd = make_register_name(instruction[20:25])
        shamt = int(instruction[7:12],2)

        rs1_access = register_list[int(re.sub(r'\D', '', rs1))]
        rs2_access = register_list[int(re.sub(r'\D', '', rs2))]
        rd_access = register_list[int(re.sub(r'\D', '', rd))]
        
        if opcode == "0010011":
            shift_map = {
                "001": ("slli", Register.lshift),
                "101": {"0000000": ("srli", Register.rlshift), "0100000": ("srai",Register.rashift)}
            }

            output = shift_map.get(funct3, "unknown instruction\n")
            
            if isinstance(output, dict):
                output = output.get(funct7, "unknown instruction\n")
            
            if isinstance(output, tuple):
                output, operation = output
                result = operation(rs1_access, shamt)
                rd_access.value = result
                
            #print(output + " " + rd + rs1 + str(shamt))

        else:
            print_rs = rd + rs1 + rs2
            output = rtype_map.get(funct3, "unknown instruction\n")
            if isinstance(output, dict):
                output = output.get(funct7, "unknown instruction\n")

            if isinstance(output, tuple):
                output, operation = output
                result = operation(rs1_access, rs2_access)  
                rd_access.value = result

            #print(output + " " + print_rs)

    def Itype(self, opcode, instruction):
        itype_map = {
            "0000011": {"000": "lb", "001": "lh", "010": ("lw", Register.lw), "100": "lbu", "101": "lhu"},
            "0010011": {"000": ("addi", Register.add), "010": ("slti", Register.slt), "011": "sltiu", "100": ("xori", Register.xor), "110": ("ori", Register.myor), "111": ("andi", Register.myand)},
            "1100111": "jalr"
        }

        immediate = instruction[0:12]
        rs1 = make_register_name(instruction[12:17])
        funct3 = instruction[17:20]
        rd = make_register_name(instruction[20:25])

        rs1_access = register_list[int(re.sub(r'\D', '', rs1))]
        rd_access = register_list[int(re.sub(r'\D', '', rd))]

        output = itype_map.get(opcode, "unknown instruction\n")

        if output == "jalr":
            rd_access.value = self.pc + 4
            self.pc = (rs1_access.value + twosint(immediate))
            self.pc -= 4
            #print(output + " " + rd + str(twosint(immediate)) + "(" + rs1 + ")") 

        if isinstance(output, dict):
            output = output.get(funct3, "unknown instruction\n")

        if isinstance(output, tuple):
            output, operation = output
            result = operation(rs1_access, twosint(immediate))
            rd_access.value = result
        
        if output == "lb" or output == "lh" or output == "lw" or output == "lbu" or output == "lhu":
            rs1 = make_register_name(instruction[12:17], 1)
            #print(output + " " + rd + str(twosint(immediate)) + "(" + rs1 + ")")

        #else:
            #print(output + " " + rd + rs1 + str(twosint(immediate)))

    def Utype(self, opcode,instruction):
        rd = instruction[20:25]
        immediate = instruction[0:20]
        print_remain = make_register_name(rd) + str(twosint(immediate)) + "000000000000"
        rd_access = register_list[int(re.sub(r'\D', '', make_register_name(rd)))]

        utype_map = {
            "0110111": "lui",
            "0010111": "auipc",
        }

        output = utype_map.get(opcode, "unknown instruction\n")
        if output == "lui":
            rd_access.value = (twosint(immediate) << 12) & 0xFFFFFFFF

        if output == "auipc":
            rd_access.value = (self.pc + (twosint(immediate) << 12)) & 0xFFFFFFFF

        #print(output + " " + print_remain)

    def Stype(self, opcode,instruction):
        stype_map = {
            "000": "sb", 
            "001": "sh", 
            "010": ("sw", Register.sw)
        }

        immediate = instruction[0:7] + instruction[20:25]
        rs2 = make_register_name(instruction[7:12])
        rs1 = make_register_name(instruction[12:17], 1)
        funct3 = instruction[17:20]

        rs1_access = register_list[int(re.sub(r'\D', '', rs1))]
        rs2_access = register_list[int(re.sub(r'\D', '', rs2))]

        output = stype_map.get(funct3, "unknown instruction\n")

        if isinstance(output, tuple):
            output, operation = output
            operation(rs1_access, rs2_access, immediate)
        
        #print(output + " " + rs2 + str(twosint(immediate))  + "(" + rs1 + ")")

    def Btype(self, opcode, instruction):
        btype_map = {
            "000": ("beq", Register.beq),
            "001": ("bne", Register.bne),
            "100": ("blt", Register.blt),
            "101": ("bge", Register.bge),
            "110": "bltu",
            "111": "bgeu"
        }

        immediate = instruction[0:1] + instruction[24:25] + instruction[1:7] + instruction[20:24] + "0"
        rs2 = make_register_name(instruction[7:12])
        rs1 = make_register_name(instruction[12:17])
        funct3 = instruction[17:20]
        
        rs1_access = register_list[int(re.sub(r'\D', '', rs1))]
        rs2_access = register_list[int(re.sub(r'\D', '', rs2))]

        output = btype_map.get(funct3, "unknown instruction\n")
        if isinstance(output, tuple):
            output, operation = output
            result = operation(rs1_access, rs2_access)

        if result == 1:
            self.pc += twosint(immediate)
            self.pc -= 4
            
        #print(output + " " + rs1 + rs2 + str(twosint(immediate)))

    def Jtype(self, opcode, instruction):
        immediate = instruction[0:1] + instruction[12:20] + instruction[11:12] + instruction[1:11] +"0"
        rd = make_register_name(instruction[20:25])
        rd_access = register_list[int(re.sub(r'\D', '', rd))]

        rd_access.value = self.pc + 4
        self.pc += twosint(immediate)
        self.pc -= 4
        #print("jal " + rd + str(twosint(immediate)))

def print_memory():
    print("Data Memory:")
    for i in range(MEMORY_SIZE):
        if data_memory[i] != 0xFF:
            print(f"0x{MEMORY_START + i:08x}: 0x{data_memory[i]:02x}")


def main():
    while True:
        init_registers()

        if (len(sys.argv[1]) <= 255 and len(sys.argv) == 3):
            instruction_file_name = sys.argv[1]
            iter = int(sys.argv[2])

            inst_count = read_binary_txt(instruction_file_name, instruction_memory)
            cpu = CPU()

            while True:
                if cpu.pc >= INSTRUCTION_MEMORY_START + min(iter * 4, inst_count):
                    break
                instruction = cpu.fetch()
                cpu.decode(instruction)
                cpu.pc += 4

            print_registers()
            break

        elif((len(sys.argv[1]) <= 255 and len(sys.argv) == 4)):
            instruction_file_name = sys.argv[1]
            data_file_name = sys.argv[2]
            iter = int(sys.argv[3])
            inst_count = read_binary_txt(instruction_file_name, instruction_memory)
            data_count = read_binary_txt(data_file_name, data_memory)
            cpu = CPU()
            
            while True:
                if cpu.pc >= INSTRUCTION_MEMORY_START + min(iter * 4, inst_count):
                    break
                instruction = cpu.fetch()
                cpu.decode(instruction)
                cpu.pc += 4

            print_registers()
            #print_memory()
            break
        
        else:
            print("please input under the 255 characters")

if __name__ == "__main__":
    main()