package main

import (
	"bufio"
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/nxadm/tail"
)

// --- Estruturas de Dados ---
type Config struct {
	ApiURL   string
	LojaID   int
	PdvID    int
	ServerIP string
}
type PdvEvent struct {
	LojaID    int                    `json:"loja_id"`
	PdvID     int                    `json:"pdv_id"`
	EventType string                 `json:"event_type"`
	Data      map[string]interface{} `json:"data"`
}
type RegexRule struct {
	Regex         string         `json:"regex"`
	EventType     string         `json:"eventType"`
	CompiledRegex *regexp.Regexp `json:"-"`
}
type RulesConfig struct {
	Version string                 `json:"version"`
	Rules   map[string][]RegexRule `json:"rules"`
}

// --- Variáveis Globais ---
var (
	currentRules     RulesConfig
	rulesMutex       sync.RWMutex
	vendaAberta      bool
	vendaAbertaMutex sync.Mutex
)

// --- Funções (loadConfig, sendEventToAPI, fetchAndCompileRules, etc.) ---
// (Estas funções permanecem as mesmas das versões anteriores e estão corretas)
func loadConfig(ariusConfPath string, pdvConfPath string) (Config, error) {
	var config Config
	cmd := exec.Command("sh", "-c", "grep '^Server=' "+ariusConfPath+" | head -n 1 | cut -d'=' -f2")
	output, err := cmd.Output()
	if err != nil {
		return config, fmt.Errorf("falha ao executar grep: %w", err)
	}
	ip := strings.TrimSpace(string(output))
	config.ServerIP = ip
	config.ApiURL = fmt.Sprintf("https://%s", ip)
	pdvFile, err := os.Open(pdvConfPath)
	if err != nil {
		return config, fmt.Errorf("erro ao abrir %s: %w", pdvConfPath, err)
	}
	defer pdvFile.Close()
	reLoja := regexp.MustCompile(`^\s*PDV_NROLOJA\s*=\s*(\d+)`)
	rePdv := regexp.MustCompile(`^\s*PDV_NROCPU\s*=\s*(\d+)`)
	scannerPdv := bufio.NewScanner(pdvFile)
	for scannerPdv.Scan() {
		line := scannerPdv.Text()
		if matches := reLoja.FindStringSubmatch(line); len(matches) > 1 {
			if id, err := strconv.Atoi(matches[1]); err == nil {
				config.LojaID = id
			}
		}
		if matches := rePdv.FindStringSubmatch(line); len(matches) > 1 {
			if id, err := strconv.Atoi(matches[1]); err == nil {
				config.PdvID = id
			}
		}
	}
	if config.LojaID == 0 {
		return config, fmt.Errorf("PDV_NROLOJA não encontrado")
	}
	if config.PdvID == 0 {
		return config, fmt.Errorf("PDV_NROCPU não encontrado")
	}
	return config, nil
}
func sendEventToAPI(client *http.Client, config Config, eventType string, data map[string]interface{}) {
	if data == nil {
		data = make(map[string]interface{})
	}
	event := PdvEvent{LojaID: config.LojaID, PdvID: config.PdvID, EventType: eventType, Data: data}
	jsonData, err := json.Marshal(event)
	if err != nil {
		log.Printf("!! Erro JSON: %v", err)
		return
	}
	req, err := http.NewRequest("POST", config.ApiURL+"/pdv/event", bytes.NewBuffer(jsonData))
	if err != nil {
		log.Printf("!! Erro Req: %v", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("!! Erro API: %v", err)
		return
	}
	defer resp.Body.Close()
	log.Printf("   -> Evento '%s' enviado. Resposta da API: %s", eventType, resp.Status)
}
func fetchAndCompileRules(client *http.Client, config Config) (RulesConfig, error) {
	var newRules RulesConfig
	resp, err := client.Get(config.ApiURL + "/config/rules")
	if err != nil {
		return newRules, fmt.Errorf("erro ao baixar rules.json: %w", err)
	}
	defer resp.Body.Close()
	if err := json.NewDecoder(resp.Body).Decode(&newRules); err != nil {
		return newRules, fmt.Errorf("erro ao decodificar rules.json: %w", err)
	}
	for logName, ruleList := range newRules.Rules {
		for i := range ruleList {
			re, err := regexp.Compile(ruleList[i].Regex)
			if err != nil {
				log.Printf("AVISO: Regex inválida para %s: '%s'.", logName, ruleList[i].Regex)
				continue
			}
			ruleList[i].CompiledRegex = re
		}
	}
	return newRules, nil
}
func autoUpdateRules(client *http.Client, config Config, wg *sync.WaitGroup) {
	defer wg.Done()
	for {
		time.Sleep(5 * time.Minute)
		resp, err := client.Get(config.ApiURL + "/config/version")
		if err != nil {
			log.Printf("ATUALIZAÇÃO: Erro ao verificar versão: %v", err)
			continue
		}
		body, err := io.ReadAll(resp.Body)
		resp.Body.Close()
		if err != nil {
			log.Printf("ATUALIZAÇÃO: Erro ao ler resposta: %v", err)
			continue
		}
		remoteVersion := strings.TrimSpace(string(body))
		rulesMutex.RLock()
		localVersion := currentRules.Version
		rulesMutex.RUnlock()
		if remoteVersion != localVersion {
			log.Printf("ATUALIZAÇÃO: Nova versão detectada! Local: '%s', Remota: '%s'.", localVersion, remoteVersion)
			newRules, err := fetchAndCompileRules(client, config)
			if err != nil {
				log.Printf("ATUALIZAÇÃO: Falha ao baixar novas regras: %v", err)
				continue
			}
			rulesMutex.Lock()
			currentRules = newRules
			rulesMutex.Unlock()
			log.Printf("ATUALIZAÇÃO: Regras atualizadas para a versão %s!", newRules.Version)
		}
	}
}
func watchOperatorStatus(client *http.Client, config Config, wg *sync.WaitGroup) {
	defer wg.Done()
	var lastOperatorID string
	for {
		cmd := exec.Command("find", "/posnet/", "-name", "OPER_*.pdv", "-mmin", "-1440", "!", "-name", "OPER_001000.pdv")
		output, err := cmd.Output()
		currentOperatorID := ""
		if err == nil && len(output) > 0 {
			re := regexp.MustCompile(`OPER_(\d+)\.pdv`)
			matches := re.FindStringSubmatch(string(output))
			if len(matches) > 1 {
				currentOperatorID = matches[1]
			}
		}
		if currentOperatorID != lastOperatorID {
			if currentOperatorID != "" {
				log.Println("==> LÓGICA: Operador logado:", currentOperatorID)
				sendEventToAPI(client, config, "UPDATE_OPERADOR", map[string]interface{}{"operador_id": currentOperatorID})
			} else {
				log.Println("==> LÓGICA: Operador deslogou.")
				sendEventToAPI(client, config, "OPERADOR_LOGOFF", nil)
			}
			lastOperatorID = currentOperatorID
		}
		time.Sleep(15 * time.Second)
	}
}

// --- SENSOR DE LOG COM O GATILHO CORRETO ---
func watchLogFile(client *http.Client, config Config, logName string, wg *sync.WaitGroup) {
	defer wg.Done()
	filename := fmt.Sprintf("/posnet/%s%s.txt", logName, time.Now().Format("0201"))
	t, err := tail.TailFile(filename, tail.Config{
		Follow: true, Location: &tail.SeekInfo{Offset: 0, Whence: io.SeekEnd},
		ReOpen: true, Poll: true,
	})
	if err != nil {
		log.Printf("ERRO FATAL ao monitorar %s: %v", filename, err)
		return
	}
	log.Printf("SENSOR LOG: Monitorando %s...", filename)

	for line := range t.Lines {
		log.Printf("[DEBUG] Linha de '%s': \"%s\"", logName, line.Text)

		ruleMatched := false

		// Lógica de estado usando o gatilho único e confiável
		if logName == "logpdv" {
			vendaAbertaMutex.Lock()
			isCurrentlyOpen := vendaAberta

			// SUA DESCOBERTA GENIAL: O gatilho único de início de venda
			if strings.Contains(line.Text, "IntegracaoServicosVenda: Processo de identificacao dos servicos de integracao finalizado.") {
				log.Printf("--> LÓGICA: Encontrado GATILHO ÚNICO de início de venda. Estado atual: %t", isCurrentlyOpen)
				if !isCurrentlyOpen {
					log.Println("==> AÇÃO: Venda estava FECHADA. Abrindo e enviando evento INICIO_VENDA...")
					vendaAberta = true
					sendEventToAPI(client, config, "INICIO_VENDA", nil)
				}
				ruleMatched = true
			} else if strings.Contains(line.Text, "Finalizou a funcao 'trocouresto' retornando '1'") {
				log.Printf("--> LÓGICA: Encontrado 'Fim de venda'. Estado atual: %t", isCurrentlyOpen)
				if isCurrentlyOpen {
					log.Println("==> AÇÃO: Venda estava ABERTA. Fechando e enviando evento FIM_VENDA...")
					vendaAberta = false
					sendEventToAPI(client, config, "FIM_VENDA", nil)
				}
				ruleMatched = true
			}
			vendaAbertaMutex.Unlock()
		}

		if ruleMatched {
			continue
		}

		// Processa as regras de captura de dados do rules.json
		rulesMutex.RLock()
		rulesForThisLog := currentRules.Rules[logName]
		rulesMutex.RUnlock()

		for _, rule := range rulesForThisLog {
			if rule.CompiledRegex == nil {
				continue
			}
			log.Printf("--> TESTANDO REGRA para evento '%s': /%s/", rule.EventType, rule.Regex)
			matches := rule.CompiledRegex.FindStringSubmatch(line.Text)
			if len(matches) > 0 {
				log.Printf("==> CORRESPONDEU! Enviando evento '%s'.", rule.EventType)
				data := make(map[string]interface{})
				for i, name := range rule.CompiledRegex.SubexpNames() {
					if i != 0 && name != "" && i < len(matches) {
						data[name] = matches[i]
					}
				}
				sendEventToAPI(client, config, rule.EventType, data)
				break
			}
		}
	}
}

func main() {
	logFile, err := os.OpenFile("/ariusmonitor/logs/pdvstate.log", os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0666)
	if err == nil {
		log.SetOutput(logFile)
	}

	log.Println("Iniciando PDVState v4.3 (Debug Gatilho Único)...")

	tr := &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: true}}
	httpClient := &http.Client{Transport: tr, Timeout: 10 * time.Second}
	var config Config
	for {
		config, err = loadConfig("/ariusmonitor/conf/zabbix_agentd.conf", "/posnet/pdv.conf")
		if err != nil || config.ServerIP == "" || config.ServerIP == "127.0.0.1" {
			log.Printf("Falha ao carregar configuração: %v. Tentando novamente em 60s...", err)
			time.Sleep(60 * time.Second)
			continue
		}
		newRules, err := fetchAndCompileRules(httpClient, config)
		if err != nil {
			log.Printf("Falha ao carregar regras iniciais: %v. Tentando novamente em 60s...", err)
			time.Sleep(60 * time.Second)
			continue
		}
		currentRules = newRules
		log.Printf("Regras iniciais carregadas com sucesso! Versão: %s", currentRules.Version)
		break
	}

	log.Printf("Configuração carregada: API=%s, Loja=%d, PDV=%d", config.ApiURL, config.LojaID, config.PdvID)
	var wg sync.WaitGroup

	wg.Add(1)
	go autoUpdateRules(httpClient, config, &wg)
	wg.Add(1)
	go watchOperatorStatus(httpClient, config, &wg)

	rulesMutex.RLock()
	for logName := range currentRules.Rules {
		wg.Add(1)
		go watchLogFile(httpClient, config, logName, &wg)
	}
	rulesMutex.RUnlock()

	log.Println("Todos os sensores iniciados. O sistema está operacional.")
	wg.Wait()
}
