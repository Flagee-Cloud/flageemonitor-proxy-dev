#include <iostream>
#include <cstdlib>
#include <dlfcn.h>
#include <cstring>
#include <ctime>
#include <csignal>
#include <unistd.h>
#include <cctype>
#include <sys/wait.h>
#include <sys/stat.h>
#include <dirent.h> // Para manipulação de diretórios
#include <libgen.h> // Para manipulação de strings de caminhos
#include <fstream> // Para manipulação de arquivos
#include <memory> // Para usar smart pointers

#define VERSION "1.7.3"
#define DTCOMPILED "2024-09-24"
#define MIN_STRING_LENGTH 4

// Definindo ponteiros de função para diferentes funções das bibliotecas SAT
using ConsultarStatusOperacionalFunc = char* (*)(int, const char*);
using ExtrairLogsFunc = char* (*)(int, const char*);
using AtualizarSoftwareSATFunc = char* (*)(int, const char*);
using DesbloquearSATFunc = char* (*)(int, const char*);
using ConfigurarInterfaceDeRede = char* (*)(int, const char*);
using AssociarAssinaturaFunc = char* (*)(int, const char*, const char*, const char*);

volatile sig_atomic_t timeout_ocorreu = false; // Variável atômica usada em signal handlers

// Tratador de sinal para lidar com SIGALRM e SIGBUS
void signal_handler(int sig) {
    if (sig == SIGALRM) {
        std::cerr << "Timeout: a biblioteca demorou demais para responder." << std::endl;
    } else if (sig == SIGBUS) {
        std::cerr << "Erro no barramento." << std::endl;
    }
}

// Tratador de sinal específico para timeouts
void alarm_handler(int sig) {
    std::cerr << "Timeout: a biblioteca demorou demais para responder." << std::endl;
    timeout_ocorreu = true;
}

// Verifica se o arquivo existe
bool file_exists(const std::string& filename) {
    struct stat buffer;
    return (stat(filename.c_str(), &buffer) == 0); // Retorna true se o arquivo existir
}

const char* codigoDeAtivacao = "123456789"; // Código de ativação do SAT
const char* lib_dirs[] = { // Lista de bibliotecas SAT
    "/posnet/libSatGer.so",
    "/posnet/libsatelgin.so",
    "/posnet/libsat-smart.so",
    "/posnet/libsatelgin-linker2.so",
    "/posnet/libsatelgin-smart.so",
    "/posnet/libsattanca.so",
    "/posnet/libbemasat.so",
    "/posnet/libsatprotocol.so",
    "/posnet/libsatid.so",
    "/posnet/libdllsatElgin2.so",
    "/posnet/libsat-linker1.so",
    "/posnet/libsat-linker2.so",
    "/posnet/libsatelgin-linker1.so",
    "/posnet/libsatelgin-linker2.so",
    "/posnet/libsatsweda.so"
};

// Enumeração para facilitar o uso dos fabricantes de SAT
enum SatFabricante {
    SAT_NONE = 0,
    SAT_DIMEP = 1,
    SAT_SWEDA = 2,
    SAT_TANCA = 3,
    SAT_GERTEC = 4,
    SAT_BEMATECH = 6,
    SAT_ELGIN = 7,
    SAT_ELGIN_LINKER2 = 10,
    SAT_ID = 12
};

// Função para obter o caminho da biblioteca SAT com base no fabricante
const char* get_library_path(int fabricante) {
    const char* primary_path;
    const char* fallback_path;

    // Define os caminhos principais e de fallback para cada fabricante
    switch (fabricante) {
        case SAT_GERTEC:
            primary_path = "/posnet/libSatGer.so";
            fallback_path = "/ariusmonitor/libs/32-bits/libSatGer.so";
            break;
        case SAT_DIMEP:
            primary_path = "/posnet/libsatprotocol.so";
            fallback_path = "/ariusmonitor/libs/32-bits/libsatprotocol.so";
            break;
        case SAT_SWEDA:
            primary_path = "/posnet/libSAT.so";
            fallback_path = "/ariusmonitor/libs/32-bits/libSAT.so";
            break;
        case SAT_TANCA:
            primary_path = "/posnet/libsattanca.so";
            fallback_path = "/ariusmonitor/libs/32-bits/libsattanca.so";
            break;
        case SAT_BEMATECH:
            primary_path = "/posnet/libbemasat.so";
            fallback_path = "/ariusmonitor/libs/32-bits/libbemasat.so";
            break;
        case SAT_ELGIN:
            primary_path = "/posnet/libsatelgin.so";
            fallback_path = "/ariusmonitor/libs/32-bits/libsatelgin.so";
            break;
        case SAT_ELGIN_LINKER2:
            primary_path = "/posnet/libsatelgin-linker2.so";
            fallback_path = "/ariusmonitor/libs/32-bits/libsatelgin-linker2.so";
            break;
        case SAT_ID:
            primary_path = "/posnet/libsatid.so";
            fallback_path = "/ariusmonitor/libs/32-bits/libsatid.so";
            break;
        default:
            return nullptr; // Se o fabricante não for reconhecido, retorna nulo
    }

    // Retorna o caminho da biblioteca, verificando se o arquivo existe
    if (file_exists(primary_path)) {
        return primary_path;
    } else if (file_exists(fallback_path)) {
        return fallback_path;
    } else {
        return nullptr; // Retorna nulo se nenhum dos caminhos existir
    }
}

// Função para validar o formato de um IP (placeholder)
bool is_valid_ip(const std::string& ip) {
    // Conta os pontos no IP e retorna verdadeiro se houver 3 pontos
    int count_dots = std::count(ip.begin(), ip.end(), '.');
    return count_dots == 3;
}

// Função auxiliar para converter uma string para minúsculas
std::string str_to_lower(const std::string& str) {
    std::string lower_str = str;
    std::transform(lower_str.begin(), lower_str.end(), lower_str.begin(), ::tolower);
    return lower_str;
}

// Função para verificar dependências de bibliotecas SAT usando o comando ldd
bool check_library_dependencies(const std::string& lib_path) {
    std::string cmd = "ldd " + lib_path + " 2>&1"; // Comando para verificar dependências
    FILE* pipe = popen(cmd.c_str(), "r"); // Abre um pipe para executar o comando
    if (!pipe) return false;

    char buffer[256];
    bool dependencies_ok = true;
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        if (strstr(buffer, "not found") != nullptr) {
            std::cerr << "Dependência faltando para " << lib_path << ": " << buffer << std::endl;
            dependencies_ok = false;
        }
    }

    pclose(pipe); // Fecha o pipe
    return dependencies_ok;
}

// Função auxiliar para verificar se uma string contém outra string, ignorando maiúsculas e minúsculas
bool contains_ignore_case(const std::string& haystack, const std::string& needle) {
    return str_to_lower(haystack).find(str_to_lower(needle)) != std::string::npos;
}

// Função para verificar a conexão com o SAT, lendo um arquivo de configuração
std::string verifica_conexao_sat(const std::string& config_path) {
    std::ifstream file(config_path, std::ios::binary); // Abre o arquivo de configuração em modo binário
    if (!file) {
        return {}; // Retorna string vazia se o arquivo não puder ser aberto
    }

    std::string previous_line, current_line, buffer;
    char ch;

    // Processa o arquivo caractere por caractere
    while (file.get(ch)) {
        if (isprint(ch) || isspace(ch)) { // Verifica se o caractere é imprimível ou um espaço
            buffer += ch;
            if (buffer.size() >= sizeof(buffer) - 1) {
                previous_line = current_line;
                current_line = buffer;
                buffer.clear();
            }
        } else if (buffer.size() >= MIN_STRING_LENGTH) { // Verifica se a string é suficientemente longa
            previous_line = current_line;
            current_line = buffer;
            buffer.clear();

            // Verifica se o código de ativação está presente e se o IP anterior é válido
            if (current_line.find(codigoDeAtivacao) != std::string::npos && is_valid_ip(previous_line)) {
                return "|SAT Rede " + previous_line; // Retorna a string contendo o IP
            }
        } else {
            buffer.clear(); // Limpa o buffer se não for válido
        }
    }

    return {}; // Retorna string vazia se nenhuma conexão válida for encontrada
}

// Função para consultar o status do SAT
std::string consulta_status_sat(const std::string& lib_path, const std::string& codigoDeAtivacao) {
    void *lib_handle = dlopen(lib_path.c_str(), RTLD_LAZY); // Abre a biblioteca SAT
    if (!lib_handle) {
        std::cerr << "Erro ao carregar " << lib_path << ": " << dlerror() << std::endl;
        return {}; // Retorna string vazia em caso de erro
    }

    // Obtém a função ConsultarStatusOperacional da biblioteca
    auto func = (ConsultarStatusOperacionalFunc)dlsym(lib_handle, "ConsultarStatusOperacional");
    if (!func) {
        std::cerr << "Erro ao encontrar a função ConsultarStatusOperacional na biblioteca " << lib_path << ": " << dlerror() << std::endl;
        dlclose(lib_handle);
        return {};
    }

    std::string resultado;
    const int max_retries = 3; // Número máximo de tentativas

    for (int attempt = 0; attempt < max_retries; ++attempt) {
        int numeroSessao = (rand() % (500999 - 500000 + 1)) + 500000; // Gera um número de sessão aleatório

        // Configura o alarme para 6 segundos
        timeout_ocorreu = false;
        signal(SIGALRM, alarm_handler);
        alarm(6);

        const char* resultado_const = func(numeroSessao, codigoDeAtivacao.c_str()); // Chama a função da biblioteca

        alarm(0); // Desativa o alarme

        // Verifica se o resultado é válido
        if (!resultado_const) {
            std::cerr << "Erro: Função retornou NULL. O SAT pode não estar conectado ou há um problema de comunicação." << std::endl;
            dlclose(lib_handle);
            return {};
        }

        // Verifica se houve erro de conexão
        if (contains_ignore_case(resultado_const, "Erro de conexão")) {
            std::cerr << "SAT não conectado ao USB. Verifique a conexão." << std::endl;
            dlclose(lib_handle);
            return {};
        }

        if (timeout_ocorreu) {
            std::cerr << "Timeout ao tentar " << lib_path << std::endl;
            break; // Sai do loop em caso de timeout
        }

        if (contains_ignore_case(resultado_const, "Resposta com Sucesso")) {
            resultado = resultado_const; // Copia o resultado da função
            break; // Sai do loop se houver sucesso
        }
    }

    dlclose(lib_handle); // Fecha a biblioteca SAT
    return resultado; // Retorna o resultado
}

int main(int argc, char *argv[]) {
    srand(time(nullptr)); // Inicializa o gerador de números aleatórios
    int fabricante = SAT_NONE;
    std::string lib_path; // Caminho da biblioteca SAT
    const char* cnpjContribuinte = nullptr;
    const char* chaveAssinatura = nullptr;
    const char* cnpjDesenvolvedora = "03995946000123";
    bool extrairLogs = false;
    bool atualizarSoftware = false;
    bool desbloquearSAT = false;
    bool associarAssinaturaFlag = false;

    // Análise dos argumentos passados ao programa
    for (int i = 1; i < argc; i++) {
        std::string arg(argv[i]);
        if (arg == "-h" || arg == "--help") {
            std::cout << "O software MonitoraSAT foi desenvolvido e é mantido por Flagee.Cloud (www.flagee.cloud)\n\n";
            std::cout << "Uso: " << argv[0] << " [opções]\n";
            std::cout << "--lib <caminho> --fabricante <id> --func <nome_funcao>\n";
            return 0;
        } else if (arg == "--fabricante" && i + 1 < argc) {
            fabricante = atoi(argv[++i]);
            lib_path = get_library_path(fabricante);
            if (lib_path.empty()) {
                std::cerr << "Fabricante inválido: " << fabricante << std::endl;
                return 1;
            }
        } else if (arg == "--lib" && i + 1 < argc) {
            lib_path = argv[++i];
        } else if (arg == "--func" && i + 1 < argc) {
            i++;
            if (std::string(argv[i]) == "AssociarAssinatura") {
                associarAssinaturaFlag = true;
            } else if (std::string(argv[i]) == "ExtrairLogs") {
                extrairLogs = true;
            } else if (std::string(argv[i]) == "DesbloquearSAT") {
                desbloquearSAT = true;
            } else if (std::string(argv[i]) == "AtualizarSoftwareSAT") {
                atualizarSoftware = true;
            }
        } else if (arg == "--cnpj-contribuinte" && i + 1 < argc) {
            cnpjContribuinte = argv[++i];
        } else if (arg == "--chave" && i + 1 < argc) {
            chaveAssinatura = argv[++i];
        } else if (arg == "--codigo" && i + 1 < argc) {
            codigoDeAtivacao = argv[++i];
        } else if (arg == "-v" || arg == "--version") {
            std::cout << "Versão do MonitoraSAT: " << VERSION << "\nCompilado em: " << DTCOMPILED << std::endl;
            return 0;
        }
    }

    // Carrega a lib na variável
    if (lib_path.empty()) {
        std::cerr << "Nenhuma biblioteca fornecida." << std::endl;
        return 1;
    }

    // Chama a função para consultar o status do SAT
    std::string resultado = consulta_status_sat(lib_path, codigoDeAtivacao);
    if (!resultado.empty()) {
        std::cout << resultado << std::endl;
    } else {
        std::cerr << "Falha ao executar a função." << std::endl;
    }

    return resultado.empty() ? 1 : 0; // Retorna 1 se houver falha, caso contrário 0
}
