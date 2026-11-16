{{- define "opsproof.validate" -}}
{{- if not (has .Values.component (list "demo" "control")) -}}
{{- fail "component must be demo or control" -}}
{{- end -}}
{{- if and .Values.controlRdsTls.enabled (ne .Values.component "control") -}}
{{- fail "RDS connection is only valid for control" -}}
{{- end -}}
{{- if and .Values.controlRdsTls.enabled (or .Values.m6.armEnabled .Values.m6.trialWorkerEnabled) -}}
{{- fail "Cloud RDS cannot enable local trial execution" -}}
{{- end -}}
{{- if and (eq .Values.environment "temporary-eks") (or .Values.recoveryEnabled .Values.kubernetesRecoveryEnabled .Values.m6.armEnabled .Values.m6.trialWorkerEnabled) -}}
{{- fail "Temporary EKS cannot enable local recovery or trial execution" -}}
{{- end -}}
{{- if and (eq .Values.environment "temporary-eks") (or (empty .Values.image.digest) (not .Values.redisTls.enabled) (and (eq .Values.component "control") (not .Values.controlRdsTls.enabled))) -}}
{{- fail "Temporary EKS requires immutable images, Redis TLS and control RDS TLS" -}}
{{- end -}}
{{- $_ := required "image.repository must be set" .Values.image.repository -}}
{{- if and .Values.m6DependencyProbeEnabled (ne .Values.component "demo") -}}
{{- fail "M6 dependency probe is only valid for demo" -}}
{{- end -}}
{{- if and .Values.m6.enabled .Values.aiEnabled -}}
{{- fail "Local M6 does not permit model calls" -}}
{{- end -}}
{{- if .Values.image.digest -}}
{{- if not (regexMatch "^sha256:[a-f0-9]{64}$" .Values.image.digest) -}}
{{- fail "image.digest must be sha256:<64 lowercase hex>" -}}
{{- end -}}
{{- else -}}
{{- $_ := required "image.tag must be set" .Values.image.tag -}}
{{- end -}}
{{- if .Values.demoDownstream.enabled -}}
{{- if ne .Values.component "demo" -}}
{{- fail "demoDownstream is only valid for demo component" -}}
{{- end -}}
{{- if not (and (regexMatch "^[0-9]{1,4}$" (toString .Values.demoDownstream.delayMs)) (le (int .Values.demoDownstream.delayMs) 2000)) -}}
{{- fail "demoDownstream.delayMs must be an integer in 0..2000" -}}
{{- end -}}
{{- end -}}
{{- if and (or .Values.m6.enabled .Values.m6.armEnabled .Values.m6.trialWorkerEnabled .Values.m6.reuseEnabled) (ne .Values.component "control") -}}
{{- fail "M6 ledger is only valid for control component" -}}
{{- end -}}
{{- if and .Values.m6.reuseEnabled (not .Values.m6.enabled) -}}
{{- fail "M6 reuse requires enabled ledger" -}}
{{- end -}}
{{- if and .Values.m6.armEnabled (not .Values.m6.trialWorkerEnabled) -}}
{{- fail "M6 arming requires the dedicated trial worker" -}}
{{- end -}}
{{- if and .Values.m6.trialWorkerEnabled (or (ne .Values.component "control") (not .Values.m6.enabled)) -}}
{{- fail "M6 trial worker requires enabled control component" -}}
{{- end -}}
{{- if and .Values.worker.recoveryManaged .Values.autoscaling.keda.enabled -}}
{{- fail "Recovery and KEDA must not own the same worker replicas" -}}
{{- end -}}
{{- if and .Values.m6.enabled (empty .Values.m6.runtimeSecretName) -}}
{{- fail "Enabled M6 requires restricted runtime secret" -}}
{{- end -}}
{{- if and .Values.autoscaling.hpa.rolloutTargetEnabled (or (ne .Values.component "demo") (not .Values.rollout.enabled) (not .Values.autoscaling.hpa.enabled)) -}}
{{- fail "Rollout HPA opt-in requires demo Rollout and enabled HPA" -}}
{{- end -}}
{{- end -}}
{{- define "opsproof.image" -}}
{{- if .Values.image.digest -}}
{{ .Values.image.repository }}@{{ .Values.image.digest }}
{{- else -}}
{{ .Values.image.repository }}:{{ .Values.image.tag }}
{{- end -}}
{{- end -}}
{{- define "opsproof.env" -}}
{{- $root := .root -}}
{{- $role := .role -}}
{{- if eq $root.Values.component "demo" }}
- secretRef: {name: opsproof-demo-runtime}
{{- if $root.Values.redisTls.enabled }}
- secretRef: {name: opsproof-demo-redis-connection}
{{- end }}
{{- if eq $role "api" }}
- secretRef: {name: opsproof-demo-inspection}
- secretRef: {name: opsproof-demo-recovery}
{{- end }}
{{- else }}
- secretRef: {name: opsproof-control-runtime}
{{- if $root.Values.m6.enabled }}
- secretRef: {name: {{ $root.Values.m6.runtimeSecretName }}}
{{- end }}
{{- if $root.Values.redisTls.enabled }}
- secretRef: {name: opsproof-control-redis-connection}
{{- end }}
{{- if eq $role "api" }}
- secretRef: {name: opsproof-control-operator}
- secretRef: {name: opsproof-control-alert}
{{- else if eq $role "evidence" }}
- secretRef: {name: opsproof-control-inspection}
{{- else if eq $role "action" }}
- secretRef: {name: opsproof-control-inspection}
- secretRef: {name: opsproof-control-recovery}
{{- end }}
{{- if $root.Values.controlRdsTls.enabled }}
# Last envFrom source wins: fail closed when RDS connection secret is absent.
- secretRef: {name: opsproof-control-rds-app-connection}
{{- end }}
{{- end }}
{{- end -}}
{{- define "opsproof.envVars" -}}
{{- $root := .root -}}
{{- $role := .role -}}
{{- if eq $root.Values.component "control" }}
{{- if $root.Values.m6.enabled }}
- name: OPSPROOF_CONTROL_M6_ENABLED
  value: "true"
- name: OPSPROOF_CONTROL_M6_ARM_ENABLED
  value: {{ $root.Values.m6.armEnabled | quote }}
- name: OPSPROOF_CONTROL_M6_REUSE_ENABLED
  value: {{ and (has $role (list "api" "evidence")) $root.Values.m6.reuseEnabled | ternary "true" "false" | quote }}
{{- end }}
- name: OPSPROOF_CONTROL_ENVIRONMENT
  value: {{ $root.Values.environment | quote }}
- name: OPSPROOF_CONTROL_KUBERNETES_OBSERVATION_ENABLED
  value: {{ and (has $role (list "api" "evidence")) $root.Values.kubernetesObservationEnabled | ternary "true" "false" | quote }}
- name: OPSPROOF_CONTROL_KUBERNETES_RECOVERY_ENABLED
  value: {{ and (has $role (list "api" "action" "evidence")) $root.Values.kubernetesRecoveryEnabled | ternary "true" "false" | quote }}
- name: OPSPROOF_CONTROL_RECOVERY_ENABLED
  value: {{ and (or (eq $role "action") (eq $role "api")) $root.Values.recoveryEnabled | ternary "true" "false" | quote }}
- name: OPSPROOF_CONTROL_AI_ENABLED
  value: {{ and (or (eq $role "evidence") (eq $role "api")) $root.Values.aiEnabled | ternary "true" "false" | quote }}
- name: OPSPROOF_CONTROL_PROMETHEUS_URL
  value: {{ $root.Values.prometheusUrl | quote }}
- name: OPSPROOF_CONTROL_ALLOWED_BROWSER_ORIGINS
  value: {{ $root.Values.cookieOrigins | quote }}
{{- end }}
{{- if and (eq $root.Values.component "demo") (eq $role "worker") $root.Values.demoDownstream.enabled }}
- {name: OPSPROOF_DOWNSTREAM_ENABLED, value: "true"}
{{- end }}
{{- if and (eq $root.Values.component "demo") (eq $role "api") $root.Values.m6DependencyProbeEnabled }}
- {name: OPSPROOF_M6_DEPENDENCY_PROBE_ENABLED, value: "true"}
{{- end }}
{{- if $root.Values.telemetry.enabled }}
- name: OTEL_EXPORTER_OTLP_ENDPOINT
  value: {{ $root.Values.telemetry.endpoint | quote }}
- {name: OTEL_EXPORTER_OTLP_PROTOCOL, value: "http/protobuf"}
- {name: OTEL_TRACES_EXPORTER, value: otlp}
- {name: OTEL_LOGS_EXPORTER, value: otlp}
- {name: OTEL_METRICS_EXPORTER, value: none}
- {name: OTEL_PYTHON_LOG_AUTO_INSTRUMENTATION, value: "true"}
- {name: OTEL_TRACES_SAMPLER, value: parentbased_traceidratio}
- name: OTEL_TRACES_SAMPLER_ARG
  value: {{ and (eq $root.Values.component "demo") $root.Values.demoDownstream.enabled | ternary "1.0" "0.25" | quote }}
- name: OTEL_SERVICE_NAME
  value: {{ printf "opsproof-%s-%s" $root.Values.component $role | quote }}
{{- end }}
{{- end -}}
{{- define "opsproof.pod" -}}
{{- $root := .root -}}
{{- $role := .role -}}
serviceAccountName: {{ $root.Release.Name }}-{{ $role }}
automountServiceAccountToken: false
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  runAsGroup: 10001
  seccompProfile: {type: RuntimeDefault}
terminationGracePeriodSeconds: 35
containers:
  - name: {{ $role }}
    image: {{ include "opsproof.image" $root | quote }}
    imagePullPolicy: {{ $root.Values.image.pullPolicy }}
    {{- if $root.Values.telemetry.enabled }}
    command: ["opentelemetry-instrument", "python", "-m", {{ ternary "opsproof_demo" "opsproof_control" (eq $root.Values.component "demo") | quote }}]
    {{- end }}
    args: [{{ ternary "dispatcher" $role (and (eq $root.Values.component "demo") (eq $role "dispatch")) | quote }}]
    envFrom:
{{ include "opsproof.env" (dict "root" $root "role" $role) | indent 6 }}
    {{- if or (eq $root.Values.component "control") $root.Values.telemetry.enabled (and (eq $root.Values.component "demo") (or (and (eq $role "worker") $root.Values.demoDownstream.enabled) (and (eq $role "api") $root.Values.m6DependencyProbeEnabled))) }}
    env:
{{ include "opsproof.envVars" (dict "root" $root "role" $role) | indent 6 }}
    {{- end }}
    resources:
{{- if eq $role "api" }}
{{ toYaml $root.Values.api.resources | indent 10 }}
{{- else if eq $role "dispatch" }}
{{ toYaml $root.Values.dispatcher.resources | indent 10 }}
{{- else }}
{{ toYaml $root.Values.worker.resources | indent 10 }}
{{- end }}
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities: {drop: [ALL]}
    volumeMounts:
      - {name: tmp, mountPath: /tmp}
      {{- if $root.Values.redisTls.enabled }}
      - {name: redis-ca, mountPath: /etc/opsproof/redis-ca, readOnly: true}
      {{- end }}
      {{- if and (eq $root.Values.component "control") $root.Values.controlRdsTls.enabled }}
      - {name: rds-ca, mountPath: /etc/opsproof/rds-ca, readOnly: true}
      {{- end }}
      {{- if and (eq $root.Values.component "control") (or (and $root.Values.kubernetesRecoveryEnabled (has $role (list "action" "evidence"))) (and $root.Values.kubernetesObservationEnabled (eq $role "evidence"))) }}
      - {name: kubernetes-identity, mountPath: /var/run/secrets/opsproof-kubernetes, readOnly: true}
      {{- end }}
    {{- if eq $role "api" }}
    ports:
      - {name: http, containerPort: 8080}
    readinessProbe:
      httpGet: {path: /health/ready, port: http}
      periodSeconds: 5
      timeoutSeconds: 3
      failureThreshold: 6
    livenessProbe:
      httpGet: {path: /health/live, port: http}
      initialDelaySeconds: 15
      periodSeconds: 10
      timeoutSeconds: 3
    {{- end }}
volumes:
  {{- if and (eq $root.Values.component "control") (or (and $root.Values.kubernetesRecoveryEnabled (has $role (list "action" "evidence"))) (and $root.Values.kubernetesObservationEnabled (eq $role "evidence"))) }}
  - name: kubernetes-identity
    projected:
      defaultMode: 0444
      sources:
        - serviceAccountToken: {path: token, expirationSeconds: 600}
        - configMap:
            name: kube-root-ca.crt
            items: [{key: ca.crt, path: ca.crt}]
  {{- end }}
  {{- if and (eq $root.Values.component "control") $root.Values.controlRdsTls.enabled }}
  - name: rds-ca
    configMap:
      name: {{ $root.Values.controlRdsTls.caConfigMapName | quote }}
      items: [{key: global-bundle.pem, path: global-bundle.pem}]
  {{- end }}
  {{- if $root.Values.redisTls.enabled }}
  - name: redis-ca
    secret:
      secretName: opsproof-redis-tls
      items: [{key: ca.crt, path: ca.crt}]
  {{- end }}
  - name: tmp
    emptyDir: {sizeLimit: 32Mi}
{{- end -}}
