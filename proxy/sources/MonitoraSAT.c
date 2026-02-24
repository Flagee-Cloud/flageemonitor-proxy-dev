#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <string.h>
#include <time.h>
#include <signal.h>
#include <unistd.h>
#include <stdbool.h>
#include <ctype.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <dirent.h> // Para manipulação de diretórios
#include <libgen.h> // Para manipulação de strings de caminhos

#define VERSION "1.7.4"
#define DTCOMPILED "2024-11-21"
#define MIN_STRING_LENGTH 4

typedef char* (*ConsultarStatusOperacionalFunc)(int, const char*);
typedef char* (*ExtrairLogsFunc)(int, const char*);
typedef char* (*AtualizarSoftwareSATFunc)(int, const char*);
typedef char* (*DesbloquearSATFunc)(int, const char*);
typedef char* (*ConfigurarInterfaceDeRede)(int, const char*);
typedef char* (*AssociarAssinaturaFunc)(int, const char*, const char*, const char*);


volatile sig_atomic_t timeout_ocorreu = false; // Use sig_atomic_t para variáveis acessadas em handlers de sinal.

// Declaração da função se estiver definida em outro lugar ou abaixo no mesmo arquivo
void signal_handler(int sig);

void signal_handler(int sig) {
    if (sig == SIGALRM) {
        fprintf(stderr, "Timeout: a biblioteca demorou demais para responder.\n");
    } else if (sig == SIGBUS) {
        fprintf(stderr, "Erro no barramento.\n");
    }
}

void alarm_handler(int sig) {
    fprintf(stderr, "Timeout: a biblioteca demorou demais para responder.\n");
    timeout_ocorreu = true;
}

bool file_exists(const char *filename) {
    struct stat buffer;
    return (stat(filename, &buffer) == 0);
}

const char* codigoDeAtivacao = "123456789";
const char* lib_dirs[] = {
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
    "/posnet/libsatsweda.so",
    "/posnet/libmfe.so"
};

typedef enum {
    SAT_NONE = 0,
    SAT_DIMEP = 1,
    SAT_SWEDA = 2,
    SAT_TANCA = 3,
    SAT_GERTEC = 4,
    SAT_BEMATECH = 6,
    SAT_ELGIN = 7,
    SAT_MFE = 9,
    SAT_ELGIN_LINKER2 = 10,
    SAT_ID = 12
} SatFabricante;

const char* get_library_path(int fabricante) {
    const char* primary_path;
    const char* fallback_path;

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
        case SAT_MFE:
            primary_path = "/posnet/libmfe.so";
            fallback_path = "/ariusmonitor/libs/32-bits/libmfe.so";
            break;
        default:
            return NULL;
    }

    if (file_exists(primary_path)) {
        return primary_path;
    } else if (file_exists(fallback_path)) {
        return fallback_path;
    } else {
        return NULL;
    }
}

bool is_valid_ip(const char *ip) {
    // Esta é uma função de placeholder.
    // Implemente aqui sua lógica de validação de IP.
    const char *ptr = ip;
    int count_dots = 0;
    while (*ptr) {
        if (*ptr == '.') count_dots++;
        ptr++;
    }
    return count_dots == 3; // Retorna verdadeiro se houver três pontos
}

// Função auxiliar para converter uma string para minúsculas
char* str_to_lower(const char* str) {
    if (!str) return NULL;
    char* lower_str = strdup(str);
    for (int i = 0; lower_str[i]; i++) {
        lower_str[i] = tolower(lower_str[i]);
    }
    return lower_str;
}

bool check_library_dependencies(const char* lib_path) {
    char cmd[1024];
    sprintf(cmd, "ldd %s 2>&1", lib_path); // Redireciona stderr para stdout
    FILE* pipe = popen(cmd, "r");
    if (!pipe) return false;  // Falha ao abrir pipe

    char buffer[256];
    bool dependencies_ok = true;
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        if (strstr(buffer, "not found") != NULL) {
            fprintf(stderr, "Dependência faltando para %s: %s", lib_path, buffer);
            dependencies_ok = false;
        }
    }

    pclose(pipe);
    return dependencies_ok;
}

// Função auxiliar para buscar uma substring insensível a maiúsculas e minúsculas
bool contains_ignore_case(const char* haystack, const char* needle) {
    if (!haystack || !needle) return false;
    char* lower_haystack = str_to_lower(haystack);
    char* lower_needle = str_to_lower(needle);
    bool result = strstr(lower_haystack, lower_needle) != NULL;
    free(lower_haystack);
    free(lower_needle);
    return result;
}

char* verifica_conexao_sat(const char *config_path) {
    FILE *file = fopen(config_path, "rb"); // Abre o arquivo em modo binário
    if (!file) {
        //fprintf(stderr, "Arquivo de configuração %s não encontrado.\n", config_path);
        return NULL;
    }

    char buffer[256];
    int index = 0;
    char previous_line[256] = {0};
    char current_line[256] = {0};
    int ch;

    while ((ch = fgetc(file)) != EOF) {
        if (isprint(ch) || isspace(ch)) { // Verifica se o caractere é imprimível ou espaço
            buffer[index++] = (char)ch;
            if (index >= sizeof(buffer) - 1) { // Evita overflow do buffer
                buffer[index] = '\0'; // Termina a string
                // Processa a string
                strcpy(previous_line, current_line);
                strcpy(current_line, buffer);
                index = 0;
            }
        } else if (index >= MIN_STRING_LENGTH) { // Considera uma string válida se tiver comprimento mínimo
            buffer[index] = '\0';
            strcpy(previous_line, current_line);
            strcpy(current_line, buffer);
            index = 0;

            if (strstr(current_line, codigoDeAtivacao) && is_valid_ip(previous_line)) {
                fclose(file);
                char *result = malloc(strlen("|SAT Rede") + strlen(previous_line) + 1);
                if (result != NULL) {
                    sprintf(result, "|SAT Rede %s", previous_line);
                    return result;
                }
            }
        } else {
            index = 0; // Reseta o índice se o caractere não for imprimível
        }
    }

    fclose(file);
    return NULL;
}


// Utilizando a função nova em consulta_status_sat
char* consulta_status_sat(const char* lib_path, const char* codigoDeAtivacao) {
    // Abre a biblioteca
    void *lib_handle = dlopen(lib_path, RTLD_LAZY);
    if (!lib_handle) {
        // Ao invés de apenas retornar a mensagem de erro, vamos imprimir e continuar
        fprintf(stderr, "Erro ao carregar %s: %s\n", lib_path, dlerror());
        return NULL;  // Retorna NULL para permitir que o loop continue tentando outras bibliotecas
    }

    // Obtém a função da biblioteca
    ConsultarStatusOperacionalFunc func = (ConsultarStatusOperacionalFunc) dlsym(lib_handle, "ConsultarStatusOperacional");
    if (!func) {
        fprintf(stderr, "Erro ao encontrar a função ConsultarStatusOperacional na biblioteca %s: %s\n", lib_path, dlerror());
        dlclose(lib_handle);
        return NULL;
    }

    char* resultado = NULL;
    const int max_retries = 3;

    for (int attempt = 0; attempt < max_retries; ++attempt) {
        int numeroSessao = (rand() % (500999 - 500000 + 1)) + 500000;

        // Configura o alarme e o tratador de sinal
        timeout_ocorreu = false;
        signal(SIGALRM, alarm_handler);
        alarm(6); // Define o tempo limite para 6 segundos

        const char *resultado_const = func(numeroSessao, codigoDeAtivacao);

        // Desativa o alarme imediatamente após a chamada da função
        alarm(0); 

        if (!resultado_const) {
            fprintf(stderr, "Erro: Função retornou NULL. O SAT pode não estar conectado ou há um problema de comunicação.\n");
            dlclose(lib_handle);  // Fecha a biblioteca para evitar vazamento de recursos
            return NULL;  // Sai da função, prevenindo o uso de um ponteiro inválido
        }

        // Verificar se a string retornada contém algum erro indicando falta de conexão
        if (strstr(resultado_const, "Erro de conexão") != NULL) {
            fprintf(stderr, "SAT não conectado ao USB. Verifique a conexão.\n");
            dlclose(lib_handle);  // Fecha a biblioteca
            return NULL;  // Sai da função
        }

        if (timeout_ocorreu) {
            fprintf(stderr, "Timeout ao tentar %s\n", lib_path);
            break;
        }

        if (resultado_const && contains_ignore_case(resultado_const, "Resposta com Sucesso")) {
            resultado = strdup(resultado_const);
            break;
        }
    }


    dlclose(lib_handle);
    return resultado;
}

int le_sat_conf(char *lib_path) {
    FILE *file = fopen("/ariusmonitor/sat.conf", "r");
    if (!file) return 0;

    if (fgets(lib_path, 255, file) == NULL) {
        fclose(file);
        return 0;
    }

    fclose(file);
    return 1;
}

void salva_caminho_biblioteca(const char* lib_path) {
    FILE *file = fopen("/ariusmonitor/sat.conf", "w");
    if (!file) {
        fprintf(stderr, "Erro ao abrir o arquivo sat.conf para escrita.\n");
        return;
    }

    fprintf(file, "%s", lib_path);
    fclose(file);
}

static const char BASE64_CHARS[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

// Função para decodificar um caractere em Base64
static inline unsigned char decode_char(char c) {
    if (c >= 'A' && c <= 'Z') return c - 'A';
    if (c >= 'a' && c <= 'z') return c - 'a' + 26;
    if (c >= '0' && c <= '9') return c - '0' + 52;
    if (c == '+') return 62;
    if (c == '/') return 63;
    return 0;
}

// Função para decodificar uma string em Base64
size_t decode_base64(unsigned char *out, const char *in) {
    size_t len = strlen(in);
    size_t olen = 0;

    for (size_t i = 0; i < len; i += 4) {
        unsigned char b[4];

        for (int j = 0; j < 4; j++) {
            b[j] = decode_char(in[i + j]);
        }

        out[olen++] = (b[0] << 2) | (b[1] >> 4);
        if (in[i + 2] != '=') {
            out[olen++] = (b[1] << 4) | (b[2] >> 2);
            if (in[i + 3] != '=') {
                out[olen++] = (b[2] << 6) | b[3];
            }
        }
    }

    return olen; // Retorna o tamanho dos dados decodificados
}

int main(int argc, char *argv[]) {
    srand(time(NULL));
    int fabricante = SAT_NONE;
    char lib_path[256] = {0};
    const char* cnpjContribuinte = NULL;
    const char* chaveAssinatura = NULL;
    const char* cnpjDesenvolvedora = "03995946000123";
    bool extrairLogs = false;
    bool atualizarSoftware = false;
    bool desbloquearSAT = false;
    bool associarAssinaturaFlag = false;
    bool deveLiberarResultado = false;

    AssociarAssinaturaFunc funcAssociarAssinatura = NULL;
    ExtrairLogsFunc funcExtrairLogs = NULL;
    AtualizarSoftwareSATFunc funcAtualizarSoftware = NULL;
    DesbloquearSATFunc funcDesbloquearSAT = NULL;
    ConsultarStatusOperacionalFunc funcConsultarStatus = NULL;

    // Análise dos argumentos
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            printf("O software MonitoraSATc foi desenvolvido e é mantido por Flagee.Cloud (www.flagee.cloud)\n\n");
            printf("Ajuda do MonitoraSATc:\n");
            printf("Uso: %s [opções]\n", argv[0]);
            printf("Opções:\n");
            printf("  --lib <caminho>            (opcional) Define o caminho para a biblioteca SAT\n");
            printf("  --fabricante <id>          (opcional) Define o caminho para a biblioteca SAT com base no ID do Arius Server\n");
            printf("  --func <nome_funcao>       Especifica a função a ser executada:\n");
            printf("                             AssociarAssinatura, ExtrairLogs, AtualizarSoftwareSAT, DesbloquearSAT\n");
            printf("  --cnpj-contribuinte <CNPJ> Define o CNPJ do contribuinte para a função AssociarAssinatura\n");
            printf("                             Apenas números, sem pontuações\n");
            printf("  --chave <chave>            Define a chave de assinatura para a função AssociarAssinatura\n");
            printf("                             Deve ser informada entre aspas\n");
            printf("  --codigo <codigo>          Define o código de ativação do SAT\n");
            printf("  -v, --version              Exibe a versão do software\n");
            printf("\n");
            printf("Exemplo:\n");
            printf("  %s --lib /caminho/para/libSat.so --fabricante <ID FABRICANTE> --func AssociarAssinatura --cnpj-contribuinte 12345678901234 --chave \"010203040506\" --codigo 123456789\n
", argv[0]);
            printf("\n");
            printf("ID de Fabricantes:\n");
            printf("DIMEP = 1, SAT_SWEDA = 2, TANCA = 3, GERTEC = 4, BEMATECH = 6, ELGIN = 7, ELGIN_LINKER2 = 10, ID = 12\n");
            return 0;
        } else if (strcmp(argv[i], "--fabricante") == 0 && i + 1 < argc) {
            fabricante = atoi(argv[++i]);
            const char* path = get_library_path(fabricante);
            if (path) {
                strncpy(lib_path, path, sizeof(lib_path) - 1);
                lib_path[sizeof(lib_path) - 1] = '\0';
            } else {
                fprintf(stderr, "Fabricante inválido: %d\n", fabricante);
                return 1;
            }
        } else if (strcmp(argv[i], "--lib") == 0 && i + 1 < argc) {
            strncpy(lib_path, argv[++i], sizeof(lib_path) - 1);
        } else if (strcmp(argv[i], "--func") == 0 && i + 1 < argc) {
            i++; // Incrementa o índice para pegar o valor do argumento
            if (strcmp(argv[i], "AssociarAssinatura") == 0) {
                associarAssinaturaFlag = true;
            } else if (strcmp(argv[i], "ExtrairLogs") == 0) {
                extrairLogs = true;
            } else if (strcmp(argv[i], "DesbloquearSAT") == 0) {
                desbloquearSAT = true;
            } else if (strcmp(argv[i], "AtualizarSoftwareSAT") == 0) {
                atualizarSoftware = true;
            }
        } else if (strcmp(argv[i], "--cnpj-contribuinte") == 0 && i + 1 < argc) {
            cnpjContribuinte = argv[++i];
        } else if (strcmp(argv[i], "--chave") == 0 && i + 1 < argc) {
            chaveAssinatura = argv[++i];
        } else if (strcmp(argv[i], "--codigo") == 0 && i + 1 < argc) {
            codigoDeAtivacao = argv[++i];
        } else if (strcmp(argv[i], "-v") == 0 || strcmp(argv[i], "--version") == 0) {
            printf("O software MonitoraSATc foi desenvolvido e é mantido por Flagee.Cloud (www.flagee.cloud)\n\n");
            printf("Versão do MonitoraSATc: %s\n", VERSION);
            printf("Compilado em: %s\n", DTCOMPILED);
            return 0;
        }
    }

    // Testando bibliotecas
    if (lib_path[0] == 0 && !le_sat_conf(lib_path)) {
        char* resultado = consulta_status_sat(lib_path, codigoDeAtivacao);
    }

    // Carrega a lib na variável
    void *lib_handle = dlopen(lib_path, RTLD_LAZY);
    if (!lib_handle) {
        fprintf(stderr, "Erro ao carregar a biblioteca %s: %s\n", lib_path, dlerror());
        return 1;
    }

    char* resultado = NULL;
    int numeroSessao = (rand() % (500999 - 500000 + 1)) + 500000;

    // Determina qual função chamar baseado nos argumentos
    if (associarAssinaturaFlag) {
        funcAssociarAssinatura = (AssociarAssinaturaFunc)dlsym(lib_handle, "AssociarAssinatura");
        if (funcAssociarAssinatura != NULL) {
            printf("Chamando a função AssociarAssinatura.\n");
            // Garantir que cnpjContribuinte e chaveAssinatura estão definidos
            if (!cnpjContribuinte || !chaveAssinatura) {
                fprintf(stderr, "CNPJ do contribuinte ou chave de assinatura não fornecidos.\n");
                dlclose(lib_handle);
                return 1;
            }
            printf("Executando Associação de Assinatura no SAT\n");
            printf("CNPJ Desenvolvedora: %s\n", cnpjDesenvolvedora);
            printf("CNPJ Contribuinte: %s\n", cnpjContribuinte);
            printf("Chave: %s\n\n", chaveAssinatura);
            printf("Aguardando retorno do SAT...\n");
            
            // Criar buffer para concatenar CNPJs
            char *cnpjsConcatenados = malloc(strlen(cnpjDesenvolvedora) + strlen(cnpjContribuinte) + 1); // +1 para o caractere nulo '\0'
            if (!cnpjsConcatenados) {
                fprintf(stderr, "Falha ao alocar memória para CNPJs concatenados.\n");
                dlclose(lib_handle);
                return 1;
            }
            strcpy(cnpjsConcatenados, cnpjDesenvolvedora);
            strcat(cnpjsConcatenados, cnpjContribuinte);
            
            resultado = funcAssociarAssinatura(numeroSessao, codigoDeAtivacao, cnpjsConcatenados, chaveAssinatura);
            
            // Liberar memória alocada para cnpjsConcatenados
            free(cnpjsConcatenados);
            cnpjsConcatenados = NULL;
        }
    } else if (extrairLogs) {
        funcExtrairLogs = (ExtrairLogsFunc)dlsym(lib_handle, "ExtrairLogs");
        if (funcExtrairLogs != NULL) {
            resultado = funcExtrairLogs(numeroSessao, codigoDeAtivacao);

            // Verifica se resultado não é NULL antes de tentar salvar no arquivo
            if (resultado != NULL) {
                // Abre um arquivo para escrita
                FILE *log_file = fopen("/ariusmonitor/log_sat/log_file.log", "wb");
                if (!log_file) {
                    fprintf(stderr, "Falha ao abrir arquivo de log para escrita.\n");
                } else {
                    // Escreve a resposta inteira no arquivo
                    fwrite(resultado, 1, strlen(resultado), log_file);
                    fclose(log_file);
                    printf("Log completo salvo com sucesso em /ariusmonitor/log_sat/log_file.log\n");
                }
            } else {
                fprintf(stderr, "A função ExtrairLogs retornou NULL.\n");
            }
        } else {
            fprintf(stderr, "%s\n", dlerror());
        }
    } else if (atualizarSoftware) {
        fprintf(stderr, "Iniciando atualização do SAT.\n");
        funcAtualizarSoftware = (AtualizarSoftwareSATFunc)dlsym(lib_handle, "AtualizarSoftwareSAT");
        if (funcAtualizarSoftware != NULL) {
            resultado = funcAtualizarSoftware(numeroSessao, codigoDeAtivacao);
        }
    } else if (desbloquearSAT) {
        fprintf(stderr, "Iniciando desbloqueio do SAT.\n");
        funcDesbloquearSAT = (DesbloquearSATFunc)dlsym(lib_handle, "DesbloquearSAT");
        if (funcDesbloquearSAT != NULL) {
            resultado = funcDesbloquearSAT(numeroSessao, codigoDeAtivacao);
        }
    } else {
        funcConsultarStatus = (ConsultarStatusOperacionalFunc)dlsym(lib_handle, "ConsultarStatusOperacional");
        if (funcConsultarStatus != NULL) {
            resultado = funcConsultarStatus(numeroSessao, codigoDeAtivacao);
        }
    }

    if (resultado) {
        printf("%s", resultado);
    } else {
        fprintf(stderr, "Falha ao executar a função.");
    }

    // Se nenhuma função for informada em --func, então testar o IP do SAT Amarrado em config.pdv
    if (!extrairLogs && !atualizarSoftware && !associarAssinaturaFlag) {
        char *conexao_sat = verifica_conexao_sat("/posnet/config.pdv");
        if (conexao_sat) {
            printf("%s", conexao_sat);
            free(conexao_sat);
            conexao_sat = NULL;
        } else {
            printf("|SAT Rede 0");
        }
    }

    // dlclose(lib_handle);
    return resultado ? 0 : 1;
}