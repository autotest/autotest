package autotest.common.ui;

import autotest.afe.IRadioButton;

import java.util.ArrayList;
import java.util.List;

public class RadioChooser {
    public static interface Display {
        public IRadioButton generateRadioButton(String groupName, String choice);
    }

    private static int groupNameCounter = 0;
    private String groupName = getFreshGroupName();
    private List<IRadioButton> radioButtons = new ArrayList<IRadioButton>();
    private IRadioButton defaultButton;

    private Display display;

    public void bindDisplay(Display display) {
        this.display = display;
    }

    private static String getFreshGroupName() {
        groupNameCounter++;
        return "group" + Integer.toString(groupNameCounter);
    }

    public void addChoice(String choice) {
        IRadioButton button = display.generateRadioButton(groupName, choice);
        if (radioButtons.isEmpty()) {
            // first button in this group
            defaultButton = button;
            button.setValue(true);
        }
        radioButtons.add(button);
    }

    public String getSelectedChoice() {
        for (IRadioButton button : radioButtons) {
            if (button.getValue()) {
                return button.getText();
            }
        }
        throw new RuntimeException("No radio button selected");
    }

    public void reset() {
        if (defaultButton != null) {
            defaultButton.setValue(true);
        }
    }

    public void setDefaultChoice(String defaultChoice) {
        defaultButton = findButtonForChoice(defaultChoice);
    }

    public void setSelectedChoice(String choice) {
        findButtonForChoice(choice).setValue(true);
    }

    private IRadioButton findButtonForChoice(String choice) {
        for (IRadioButton button : radioButtons) {
            if (button.getText().equals(choice)) {
                return button;
            }
        }
        throw new RuntimeException("No such choice found: " + choice);
    }
}
