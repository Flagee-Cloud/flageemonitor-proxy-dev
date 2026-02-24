// FilaPDVClient.cpp
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <cstring>
#include <cstdlib>
#include <chrono>
#include <thread>
#include <ctime>
#include <vector>
#include <algorithm>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <cstdio>  // para popen

using namespace std;

// Versão atual do software
const string CURRENT_VERSION = "0.1.0";

// Função que obtém a versão remota a partir do repositório
string getLatestVersion() {
    // Executa o comando que baixa o conteúdo do arquivo de versão
    string command = "wget -qO- http://repo.ariusmonitor.flagee.cloud/versao_filadpvclient.txt";
    FILE* pipe = popen(command.c_str(), "r");
    if (!pipe) {
        cerr << "Falha ao executar comando para obter versão remota." << endl;
        return "";
    }
    char buffer[128];
    string result;
    while (fgets(buffer, sizeof(buffer), pipe) != NULL) {
        result += buffer;
    }
    pclose(pipe);
    // Remove quebras de linha e espaços em branco
    result.erase(remove(result.begin(), result.end(), '\n'), result.end());
    result.erase(remove(result.begin(), result.end(), '\r'), result.end());
    return result;
}

// Função auxiliar para dividir a versão (ex: "0.1.0") em inteiros
vector<int> splitVersion(const string &version) {
    vector<int> nums;
    stringstream ss(version);
    string token;
    while(getline(ss, token, '.')) {
        nums.push_back(atoi(token.c_str()));
    }
    return nums;
}

// Compara as versões; retorna true se latestVersion for superior à currentVersion
bool isUpdateAvailable(const string &currentVersion, const string &latestVersion) {
    vector<int> curr = splitVersion(currentVersion);
    vector<int> latest = splitVersion(latestVersion);
    size_t len = max(curr.size(), latest.size());
    for (size_t i = 0; i < len; i++) {
        int c = (i < curr.size() ? curr[i] : 0);
        int l = (i < latest.size() ? latest[i] : 0);
        if (l > c) return true;
        else if (l < c) return false;
    }
    return false;
}

// Função que realiza o download da nova versão e invoca o script de atualização
void performUpdate() {
    cout << "Nova versão disponível! Realizando atualização..." << endl;
    
    // Baixa o novo binário do client
    int ret = system("wget -q http://repo.ariusmonitor.flagee.cloud/FilaPDVClient -O /ariusmonitor/FilaPDVClient.new");
    if (ret != 0) {
        cerr << "Falha no download da nova versão." << endl;
        return;
    }
    
    // Chama o script de atualização (update.sh deve estar no mesmo diretório e ser executável)
    ret = system("sh /ariusmonitor/update_filapdvclient.sh /ariusmonitor/FilaPDVClient.new /ariusmonitor/FilaPDVClient");
    if (ret != 0) {
        cerr << "Falha na execução do script de atualização." << endl;
        return;
    }
    
    // Após atualização, encerra o processo atual para que o novo binário seja iniciado pelo script
    exit(0);
}

// Lê o arquivo de configuração e retorna o valor da variável PDV_NROCPU
string getPDVNumber(const string &configFilePath) {
    ifstream confFile(configFilePath);
    if (!confFile) {
        cerr << "Erro ao abrir arquivo de configuração: " << configFilePath << endl;
        return "";
    }
    string line;
    while (getline(confFile, line)) {
        if (line.find("PDV_NROCPU") != string::npos) {
            size_t pos = line.find("=");
            if (pos != string::npos) {
                string value = line.substr(pos + 1);
                value.erase(0, value.find_first_not_of(" \t"));
                value.erase(value.find_last_not_of(" \t") + 1);
                return value;
            }
        }
    }
    return "";
}

// Testa a conexão com o servidor utilizando IP e porta
bool testConnection(const string &serverIP, int serverPort) {
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        cerr << "Erro ao criar socket para teste de conexão." << endl;
        return false;
    }
    struct sockaddr_in serv_addr;
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(serverPort);
    if (inet_pton(AF_INET, serverIP.c_str(), &serv_addr.sin_addr) <= 0) {
        cerr << "Endereço inválido para teste." << endl;
        close(sock);
        return false;
    }
    if (connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
        cerr << "Falha na conexão com o servidor durante o teste." << endl;
        close(sock);
        return false;
    }
    cout << "Conexão com o servidor estabelecida com sucesso." << endl;
    close(sock);
    return true;
}

// Função para conectar e enviar mensagem ao servidor
bool sendMessage(const string &serverIP, int serverPort, const string &message) {
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        cerr << "Erro na criação do socket." << endl;
        return false;
    }
    struct sockaddr_in serv_addr;
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_port = htons(serverPort);
    if (inet_pton(AF_INET, serverIP.c_str(), &serv_addr.sin_addr) <= 0) {
        cerr << "Endereço inválido/ não suportado." << endl;
        close(sock);
        return false;
    }
    if (connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) < 0) {
        cerr << "Conexão falhou." << endl;
        close(sock);
        return false;
    }
    send(sock, message.c_str(), message.size(), 0);
    cout << "Mensagem enviada para o servidor: " << message << endl;
    close(sock);
    return true;
}

int main(int argc, char const *argv[]) {
    // Uso: ./FilaPDVClient <IP do servidor> <Porta do servidor> [metodo/identificador]
    if (argc < 3) {
        cerr << "Uso: " << argv[0] << " <IP do servidor> <Porta do servidor> [metodo ou identificador]" << endl;
        return 1;
    }
    
    string serverIP = argv[1];
    int serverPort = atoi(argv[2]);
    
    // Testa a conexão com o servidor e exibe o resultado
    if (!testConnection(serverIP, serverPort)) {
        cerr << "Falha na conexão com o servidor. Encerrando o programa." << endl;
        return 1;
    }
    
    // Determina o modo de operação: se não for informado ou for "ariuspdv", usa esse modo; caso contrário, envia imediatamente o identificador informado
    bool isAriuspdv = true;
    if (argc >= 4) {
        string mode = argv[3];
        if (mode != "ariuspdv")
            isAriuspdv = false;
    }
    
    // Thread de auto update: verifica a cada 10 minutos se há nova versão
    thread updater([&]() {
        while (true) {
            this_thread::sleep_for(chrono::minutes(10));
            string latestVersion = getLatestVersion();
            if (!latestVersion.empty() && isUpdateAvailable(CURRENT_VERSION, latestVersion)) {
                cout << "Versão remota (" << latestVersion << ") é superior à atual (" << CURRENT_VERSION << ")." << endl;
                performUpdate();
            } else {
                cout << "Nenhuma atualização disponível. Versão atual: " << CURRENT_VERSION << endl;
            }
        }
    });
    updater.detach();
    
    if (isAriuspdv) {
        // Modo ariuspdv: lê a configuração e monitora o arquivo de log
        string pdvNumber = getPDVNumber("/posnet/pdv.conf");
        if (pdvNumber.empty()) {
            cerr << "Não foi possível obter PDV_NROCPU do arquivo de configuração." << endl;
            return 1;
        }
        
        // Obtém a data atual no formato ddMM (dia e mês com 2 dígitos)
        auto now = chrono::system_clock::now();
        time_t t_now = chrono::system_clock::to_time_t(now);
        struct tm *timeinfo = localtime(&t_now);
        char dateBuffer[5]; // "ddMM"
        strftime(dateBuffer, sizeof(dateBuffer), "%d%m", timeinfo);
        string dateStr(dateBuffer);
        
        // Monta o caminho do arquivo de log
        string logFilePath = "/posnet/logpdv" + dateStr + ".txt";
        cout << "Monitorando arquivo: " << logFilePath << endl;
        
        ifstream logFile(logFilePath);
        if (!logFile) {
            cerr << "Erro ao abrir arquivo de log: " << logFilePath << endl;
            return 1;
        }
        // Posiciona o ponteiro no final para ler somente as novas linhas
        logFile.seekg(0, ios::end);
        string line;
        
        // Loop infinito para monitorar o arquivo até que o processo seja cancelado
        while (true) {
            while (getline(logFile, line)) {
                if (line.find("CAIXA LIVRE") != string::npos) {
                    sendMessage(serverIP, serverPort, pdvNumber);
                }
            }
            logFile.clear();
            this_thread::sleep_for(chrono::milliseconds(500));
        }
    } else {
        // Modo manual: o terceiro argumento é considerado o identificador do PDV e a mensagem é enviada imediatamente
        string pdvID = argv[3];
        sendMessage(serverIP, serverPort, pdvID);
    }
    
    return 0;
}
