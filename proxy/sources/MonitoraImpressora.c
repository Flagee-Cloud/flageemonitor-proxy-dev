#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>

// Marcador de versão
#define VERSION "1.3.0" // Lógica mais segura, sem chamada de status C++

// Funções alvo confirmadas
const char *CREATE_FUNCTION_NAME = "create";
const char *DESTROY_FUNCTION_NAME = "destroy";
// REMOVIDO: Não vamos mais chamar a função de status diretamente

// Tipos das funções que vamos carregar
typedef int (*PrinterCreateFunction)(const char *, int);
typedef int (*PrinterDestroyFunction)(int);
// REMOVIDO: O tipo da função de status não é mais necessário

// ALTERADO: A lista de portas agora contém apenas caminhos de dispositivo reais.
// Removemos "USB" e "SERIAL" genéricos para forçar um teste de comunicação real.
const char *COMMON_PORTS[] = {
    "/dev/usb/lp0",
    "/dev/lp0",
    "/dev/usb/lp1",
    "/dev/lp1",
    "/dev/ttyUSB0",
    "/dev/ttyUSB1",
    "/dev/ttyS0",
    "/dev/ttyS1",
    NULL
};

// Função para imprimir a saída em JSON (sem alterações)
void print_json_output(const char *status, const char *port_found, const char *error_msg) {
    printf("{\n");
    printf("  \"program_version\": \"%s\",\n", VERSION);
    printf("  \"status\": \"%s\",\n", status);
    printf("  \"port\": \"%s\",\n", port_found ? port_found : "none");
    printf("  \"details\": {\n");
    printf("    \"manufacturer\": \"unknown\",\n");
    printf("    \"model\": \"unknown\",\n");
    printf("    \"firmware_version\": \"unknown\"\n");
    printf("  },\n");
    printf("  \"error\": \"%s\"\n", error_msg ? error_msg : "");
    printf("}\n");
}


int main(int argc, char *argv[]) {
    // Parsing de argumentos (sem alterações)
    int debug_mode = 0;
    int simple_output = 0;
    const char *lib_path = NULL;
    const char *device_path = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--debug") == 0) {
            debug_mode = 1;
        } else if (strcmp(argv[i], "--simple-output") == 0) {
            simple_output = 1;
        } else if (strcmp(argv[i], "--version") == 0) {
            printf("MonitoraImpressora Versao %s\n", VERSION);
            return 0;
        } else if (!lib_path) {
            lib_path = argv[i];
        } else if (!device_path) {
            device_path = argv[i];
        }
    }

    if (!lib_path) {
        fprintf(stderr, "Erro: Caminho da biblioteca nao fornecido.\n");
        fprintf(stderr, "Uso: %s [--debug] [--simple-output] [--version] /caminho/lib.so [porta]\n", argv[0]);
        return 1;
    }
    
    if (debug_mode) fprintf(stderr, "--- MODO DEBUG ATIVADO ---\nVersao do programa: %s\n", VERSION);

    void *lib_handle = dlopen(lib_path, RTLD_LAZY);
    if (!lib_handle) {
        char error_buffer[512];
        snprintf(error_buffer, sizeof(error_buffer), "Erro ao carregar a biblioteca '%s': %s", lib_path, dlerror());
        if (simple_output) { printf("0\n"); } 
        else { print_json_output("offline", NULL, error_buffer); }
        return 1;
    }
    dlerror();

    PrinterCreateFunction create_func = (PrinterCreateFunction) dlsym(lib_handle, CREATE_FUNCTION_NAME);
    PrinterDestroyFunction destroy_func = (PrinterDestroyFunction) dlsym(lib_handle, DESTROY_FUNCTION_NAME);

    // ALTERADO: Não carregamos mais a função de status
    if (!create_func || !destroy_func) {
        const char* err_msg = "Nao foi possivel encontrar as funcoes 'create' e/ou 'destroy'.";
        if (debug_mode) fprintf(stderr, "Erro: %s\n", err_msg);
        if (simple_output) { printf("0\n"); }
        else { print_json_output("offline", NULL, err_msg); }
        dlclose(lib_handle);
        return 1;
    }

    int printer_handle = 0;
    const char *port_found = NULL;

    // Lógica de busca de porta (a mesma, mas agora mais eficaz)
    if (device_path && device_path[0] != '\0') {
        if (debug_mode) fprintf(stderr, "Verificando porta especifica: %s\n", device_path);
        printer_handle = create_func(device_path, 0);
        if (printer_handle > 0) port_found = device_path;
    } else {
        if (debug_mode) fprintf(stderr, "Nenhuma porta especificada. Verificando portas de dispositivo reais...\n");
        for (int i = 0; COMMON_PORTS[i] != NULL; i++) {
            const char* current_port = COMMON_PORTS[i];
            if (debug_mode) fprintf(stderr, "  -> Tentando porta: %s\n", current_port);
            printer_handle = create_func(current_port, 0);
            if (printer_handle > 0) {
                port_found = current_port;
                if (debug_mode) fprintf(stderr, "Impressora conectada com sucesso em '%s'! Handle: %d\n", port_found, printer_handle);
                break;
            }
        }
    }
    
    // Lógica de verificação final SIMPLIFICADA
    if (printer_handle > 0) {
        // Se create() funcionou em um dispositivo real, consideramos ONLINE.
        if (debug_mode) fprintf(stderr, "Impressora ONLINE. Fechando conexao (handle: %d)...\n", printer_handle);
        destroy_func(printer_handle);
        if (simple_output) { printf("1\n"); }
        else { print_json_output("online", port_found, NULL); }
        dlclose(lib_handle);
        return 0; // Sucesso
    } else {
        const char* err_msg = "Nenhuma impressora encontrada/conectada nas portas de dispositivo.";
        if (debug_mode) fprintf(stderr, "%s\n", err_msg);
        if (simple_output) { printf("0\n"); }
        else { print_json_output("offline", NULL, err_msg); }
        dlclose(lib_handle);
        return 1; // Falha
    }
}