package com.aetheramr.receiver;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final long MAX_RECEIPT_BYTES = 10L * 1024L * 1024L;
    private static final int BUFFER_SIZE = 64 * 1024;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private TokenVault tokenVault;
    private Uri sharedUri;
    private String sharedName = "comprobante";
    private String sharedType = "application/octet-stream";
    private long sharedSize = -1;
    private boolean busy;

    private LinearLayout loginPanel;
    private EditText usernameInput;
    private EditText passwordInput;
    private Button loginButton;
    private Button sendButton;
    private Button logoutButton;
    private ProgressBar progress;
    private TextView fileName;
    private TextView fileDetail;
    private TextView statusText;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);
        tokenVault = new TokenVault(this);
        bindViews();
        ((TextView) findViewById(R.id.versionLabel)).setText(
            "Versión " + BuildConfig.VERSION_NAME
        );
        loginButton.setOnClickListener(view -> logIn());
        sendButton.setOnClickListener(view -> uploadReceipt());
        logoutButton.setOnClickListener(view -> {
            tokenVault.clear();
            setStatus("Sesión cerrada. Inicia sesión para volver a compartir.", false);
            renderSession();
        });
        acceptIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        acceptIntent(intent);
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }

    private void bindViews() {
        loginPanel = findViewById(R.id.loginPanel);
        usernameInput = findViewById(R.id.username);
        passwordInput = findViewById(R.id.password);
        loginButton = findViewById(R.id.loginButton);
        sendButton = findViewById(R.id.sendButton);
        logoutButton = findViewById(R.id.logoutButton);
        progress = findViewById(R.id.progress);
        fileName = findViewById(R.id.fileName);
        fileDetail = findViewById(R.id.fileDetail);
        statusText = findViewById(R.id.status);
    }

    private void acceptIntent(Intent intent) {
        sharedUri = extractSharedUri(intent);
        if (sharedUri == null) {
            fileName.setText("Comparte aquí una imagen o un PDF");
            fileDetail.setText(
                "Desde WhatsApp elige Compartir y después Aether Pagos."
            );
            renderSession();
            return;
        }

        readSharedMetadata(intent);
        fileName.setText(sharedName);
        String sizeText = sharedSize >= 0
            ? String.format(Locale.US, "%.1f MB", sharedSize / 1024d / 1024d)
            : "tamaño por validar";
        fileDetail.setText(sharedType + " · " + sizeText);

        if (!isSupportedType(sharedType)) {
            setStatus("Solo se aceptan imágenes o archivos PDF.", true);
            sharedUri = null;
        } else if (sharedSize > MAX_RECEIPT_BYTES) {
            setStatus("El comprobante supera el límite de 10 MB.", true);
            sharedUri = null;
        }
        renderSession();
        if (sharedUri != null && tokenVault.get() != null) {
            uploadReceipt();
        }
    }

    @SuppressWarnings("deprecation")
    private Uri extractSharedUri(Intent intent) {
        if (intent == null) return null;
        String action = intent.getAction();
        if (Intent.ACTION_SEND.equals(action)) {
            Uri stream = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (stream != null) return stream;
        }
        if (Intent.ACTION_SEND_MULTIPLE.equals(action)) {
            ArrayList<Uri> streams = intent.getParcelableArrayListExtra(
                Intent.EXTRA_STREAM
            );
            if (streams != null && !streams.isEmpty()) return streams.get(0);
        }
        ClipData clipData = intent.getClipData();
        if (clipData != null && clipData.getItemCount() > 0) {
            return clipData.getItemAt(0).getUri();
        }
        return null;
    }

    private void readSharedMetadata(Intent intent) {
        String detectedType = getContentResolver().getType(sharedUri);
        if (detectedType == null) detectedType = intent.getType();
        if (detectedType != null) sharedType = detectedType.toLowerCase(Locale.ROOT);

        try (Cursor cursor = getContentResolver().query(
            sharedUri,
            new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE},
            null,
            null,
            null
        )) {
            if (cursor != null && cursor.moveToFirst()) {
                int nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                int sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE);
                if (nameIndex >= 0 && !cursor.isNull(nameIndex)) {
                    sharedName = cursor.getString(nameIndex);
                }
                if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) {
                    sharedSize = cursor.getLong(sizeIndex);
                }
            }
        } catch (RuntimeException ignored) {
            // Algunos proveedores solo permiten abrir el flujo; el servidor
            // vuelve a validar tipo y tamaño antes de aceptar el archivo.
        }
    }

    private boolean isSupportedType(String type) {
        return type != null && (
            type.startsWith("image/") || "application/pdf".equals(type)
        );
    }

    private void renderSession() {
        boolean authenticated = tokenVault.get() != null;
        loginPanel.setVisibility(authenticated ? View.GONE : View.VISIBLE);
        logoutButton.setVisibility(authenticated ? View.VISIBLE : View.GONE);
        sendButton.setVisibility(
            authenticated && sharedUri != null ? View.VISIBLE : View.GONE
        );
        setBusy(busy);
    }

    private void setBusy(boolean value) {
        busy = value;
        progress.setVisibility(value ? View.VISIBLE : View.GONE);
        loginButton.setEnabled(!value);
        sendButton.setEnabled(!value);
        logoutButton.setEnabled(!value);
    }

    private void logIn() {
        String username = usernameInput.getText().toString().trim();
        String password = passwordInput.getText().toString();
        if (username.isEmpty() || password.isEmpty()) {
            setStatus("Escribe tu usuario y contraseña de Aether.", true);
            return;
        }
        setBusy(true);
        setStatus("Conectando con Aether…", false);
        executor.execute(() -> {
            try {
                String token = requestToken(username, password);
                tokenVault.put(token);
                runOnUiThread(() -> {
                    passwordInput.setText("");
                    setBusy(false);
                    renderSession();
                    if (sharedUri != null) uploadReceipt(token);
                    else setStatus("Receptor conectado correctamente.", false);
                });
            } catch (Exception exception) {
                runOnUiThread(() -> {
                    setBusy(false);
                    setStatus(readableError(exception), true);
                });
            }
        });
    }

    private String requestToken(String username, String password) throws Exception {
        HttpURLConnection connection = openConnection("/api/v1/auth/login");
        connection.setRequestMethod("POST");
        connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        connection.setDoOutput(true);
        JSONObject request = new JSONObject();
        request.put("username", username);
        request.put("password", password);
        try (OutputStream output = connection.getOutputStream()) {
            output.write(request.toString().getBytes(StandardCharsets.UTF_8));
        }
        int responseCode = connection.getResponseCode();
        JSONObject response = readJsonResponse(connection, responseCode);
        if (responseCode != HttpURLConnection.HTTP_OK) {
            throw new ApiException(responseCode, response.optString(
                "detail",
                "No fue posible iniciar sesión."
            ));
        }
        String token = response.optString("access_token", "");
        if (token.isEmpty()) throw new IOException("Aether no devolvió una sesión válida.");
        return token;
    }

    private void uploadReceipt() {
        uploadReceipt(tokenVault.get());
    }

    private void uploadReceipt(String token) {
        if (sharedUri == null || token == null || busy) return;
        setBusy(true);
        setStatus("Enviando comprobante a Aether…", false);
        executor.execute(() -> {
            try {
                String launchPath = sendMultipart(token);
                runOnUiThread(() -> {
                    setBusy(false);
                    setStatus("Comprobante recibido. Abriendo Aether…", false);
                    Intent openAether = new Intent(
                        Intent.ACTION_VIEW,
                        Uri.parse(BuildConfig.AETHER_BASE_URL + launchPath)
                    );
                    startActivity(openAether);
                    finish();
                });
            } catch (ApiException exception) {
                if (exception.statusCode == HttpURLConnection.HTTP_UNAUTHORIZED) {
                    tokenVault.clear();
                }
                runOnUiThread(() -> {
                    setBusy(false);
                    renderSession();
                    setStatus(
                        exception.statusCode == HttpURLConnection.HTTP_UNAUTHORIZED
                            ? "La sesión venció. Inicia sesión y el comprobante se enviará de nuevo."
                            : readableError(exception),
                        true
                    );
                });
            } catch (Exception exception) {
                runOnUiThread(() -> {
                    setBusy(false);
                    setStatus(readableError(exception), true);
                });
            }
        });
    }

    private String sendMultipart(String token) throws Exception {
        String boundary = "AetherReceipt" + System.currentTimeMillis();
        HttpURLConnection connection = openConnection("/api/v1/payments/shared-receipts");
        connection.setRequestMethod("POST");
        connection.setRequestProperty("Authorization", "Bearer " + token);
        connection.setRequestProperty("X-Aether-Session", token);
        connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
        connection.setChunkedStreamingMode(BUFFER_SIZE);
        connection.setDoOutput(true);

        String safeName = sharedName.replace("\"", "_").replace("\r", "_").replace("\n", "_");
        String header = "--" + boundary + "\r\n"
            + "Content-Disposition: form-data; name=\"proof_file\"; filename=\"" + safeName + "\"\r\n"
            + "Content-Type: " + sharedType + "\r\n\r\n";
        long copied = 0;
        try (
            OutputStream output = new BufferedOutputStream(connection.getOutputStream());
            InputStream input = new BufferedInputStream(
                getContentResolver().openInputStream(sharedUri)
            )
        ) {
            output.write(header.getBytes(StandardCharsets.UTF_8));
            byte[] buffer = new byte[BUFFER_SIZE];
            int read;
            while ((read = input.read(buffer)) != -1) {
                copied += read;
                if (copied > MAX_RECEIPT_BYTES) {
                    throw new IOException("El comprobante supera el límite de 10 MB.");
                }
                output.write(buffer, 0, read);
            }
            output.write(("\r\n--" + boundary + "--\r\n").getBytes(StandardCharsets.UTF_8));
        }

        int responseCode = connection.getResponseCode();
        JSONObject response = readJsonResponse(connection, responseCode);
        if (responseCode != HttpURLConnection.HTTP_CREATED) {
            throw new ApiException(responseCode, response.optString(
                "detail",
                "Aether no pudo recibir el comprobante."
            ));
        }
        String launchPath = response.optString("launch_path", "");
        if (!launchPath.startsWith("/app/")) {
            throw new IOException("Aether devolvió una dirección de apertura inválida.");
        }
        return launchPath;
    }

    private HttpURLConnection openConnection(String path) throws IOException {
        URL url = new URL(BuildConfig.AETHER_BASE_URL + path);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        connection.setConnectTimeout(20_000);
        connection.setReadTimeout(40_000);
        connection.setRequestProperty("Accept", "application/json");
        connection.setRequestProperty(
            "User-Agent",
            "Aether-Android-Receiver/" + BuildConfig.VERSION_NAME
        );
        connection.setUseCaches(false);
        connection.setInstanceFollowRedirects(false);
        return connection;
    }

    private JSONObject readJsonResponse(
        HttpURLConnection connection,
        int statusCode
    ) throws Exception {
        InputStream source = statusCode >= 400
            ? connection.getErrorStream()
            : connection.getInputStream();
        if (source == null) return new JSONObject();
        try (InputStream input = source; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8 * 1024];
            int read;
            while ((read = input.read(buffer)) != -1 && output.size() < 1024 * 1024) {
                output.write(buffer, 0, read);
            }
            String body = output.toString(StandardCharsets.UTF_8.name());
            return body.isEmpty() ? new JSONObject() : new JSONObject(body);
        }
    }

    private String readableError(Exception exception) {
        String message = exception.getMessage();
        return message == null || message.trim().isEmpty()
            ? "No fue posible comunicarse con Aether. Revisa la conexión e inténtalo de nuevo."
            : message;
    }

    private void setStatus(String message, boolean error) {
        statusText.setText(message);
        statusText.setTextColor(
            error ? Color.rgb(255, 120, 133) : Color.rgb(155, 181, 210)
        );
    }

    private static final class ApiException extends Exception {
        final int statusCode;

        ApiException(int statusCode, String message) {
            super(message);
            this.statusCode = statusCode;
        }
    }
}
