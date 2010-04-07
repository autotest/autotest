package autotest.planner;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.event.dom.client.HasKeyPressHandlers;
import com.google.gwt.event.dom.client.KeyCodes;
import com.google.gwt.event.dom.client.KeyPressEvent;
import com.google.gwt.event.dom.client.KeyPressHandler;
import com.google.gwt.user.client.ui.HasText;

public class TestPlanSelector implements ClickHandler, KeyPressHandler {
    
    public static interface Display {
        public HasText getInputText();
        public HasClickHandlers getShowButton();
        public HasKeyPressHandlers getInputField();
    }
    
    
    private Display display;
    private String selectedPlan;
    
    public void bindDisplay(Display display) {
        this.display = display;
        display.getShowButton().addClickHandler(this);
        display.getInputField().addKeyPressHandler(this);
    }
    
    @Override
    public void onClick(ClickEvent event) {
        selectPlan();
    }
    
    @Override
    public void onKeyPress(KeyPressEvent event) {
        if (event.getCharCode() == KeyCodes.KEY_ENTER) {
            selectPlan();
        }
    }
    
    private void selectPlan() {
        selectedPlan = display.getInputText().getText();
    }
    
    public String getSelectedPlan() {
        return selectedPlan;
    }
}
