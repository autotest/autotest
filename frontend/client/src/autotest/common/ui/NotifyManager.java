package autotest.common.ui;

import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.DisclosurePanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.PopupPanel;
import com.google.gwt.user.client.ui.RootPanel;
import com.google.gwt.user.client.ui.TextArea;

/**
 * A singleton class to manage popup notifications, including error messages and
 * the "loading..." box.
 */
public class NotifyManager {
    // singleton
    public static final NotifyManager theInstance = new NotifyManager();
    
    static class NotifyBox {
        protected PopupPanel panel;
        protected Label message = new Label();
        
        public NotifyBox(boolean autoHide) {
            message.setStyleName("notify");
            panel = new PopupPanel(autoHide);
            panel.add(message);
        }
        
        public void addStyle(String style) {
            message.addStyleName(style);
        }
        
        public void hide() {
            panel.hide();
        }
        
        public void show() {
            panel.setPopupPosition(0, 0);
            panel.show();
        }
        
        public void showMessage(String messageString) {
            message.setText(messageString);
            show();
        }
    }
    
    static class ErrorLog extends Composite {
        protected DisclosurePanel disclosurePanel = 
            new DisclosurePanel("Error log");
        protected TextArea errorTextArea = new TextArea();
        
        public ErrorLog() {
            errorTextArea.setCharacterWidth(120);
            errorTextArea.setVisibleLines(30);
            errorTextArea.setReadOnly(true);
            disclosurePanel.add(errorTextArea);
            initWidget(disclosurePanel);
        }
        
        public void logError(String error) {
            String errorText = errorTextArea.getText();
            if (!errorText.equals(""))
                errorText += "\n------------------------------\n";
            errorText += error;
            errorTextArea.setText(errorText);
        }
    }
    
    protected NotifyBox errorNotify = new NotifyBox(true);
    protected NotifyBox messageNotify = new NotifyBox(true);
    protected NotifyBox loadingNotify = new NotifyBox(false);
    protected ErrorLog errorLog = new ErrorLog();
    private int loadingCount = 0;
    
    private NotifyManager() {
        errorNotify.addStyle("error");
    }
    
    /**
     * Should be called a page loading time.
     */
    public void initialize() {
        errorNotify.hide();
        messageNotify.hide();
        
        RootPanel.get("error_log").add(errorLog);
        errorLog.setVisible(false);
    }
    
    public static NotifyManager getInstance() {
        return theInstance;
    }
    
    /**
     * Show an error message.
     */
    public void showError(String error, String logMessage) {
        String errorLogText = error;
        if (logMessage != null)
            errorLogText += "\n" + logMessage; 
        errorNotify.showMessage(error);
        errorLog.logError(errorLogText);
        errorLog.setVisible(true);
    }
    
    public void showError(String error) {
        showError(error, null);
    }
    
    /**
     * Show a notification message.
     */
    public void showMessage(String message) {
        messageNotify.showMessage(message);
    }
    
    /**
     * Set whether the loading box is displayed or not.
     */
    public void setLoading(boolean visible) {
        if (visible) {
            if (loadingCount == 0) {
                loadingNotify.showMessage("Loading...");
            }
            loadingCount++;
        } else {
            loadingCount--;
            if (loadingCount == 0) {
                loadingNotify.hide();
            }
        }
    }
}
