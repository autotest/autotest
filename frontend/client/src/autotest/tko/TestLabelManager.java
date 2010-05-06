package autotest.tko;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.SimpleCallback;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.ui.NotifyManager;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Anchor;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.DialogBox;
import com.google.gwt.user.client.ui.HTML;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.ListBox;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.StackPanel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;

public class TestLabelManager implements ClickHandler {
    public static final String INVALIDATED_LABEL = "invalidated";
    private static final String ADD_TEXT = "Add label";
    private static final String REMOVE_TEXT = "Remove label";
    private static final int STACK_SELECT = 0, STACK_CREATE = 1;

    private static final TestLabelManager theInstance = new TestLabelManager();

    private static final JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    private static NotifyManager notifyManager = NotifyManager.getInstance();
    private static StaticDataRepository staticData = StaticDataRepository.getRepository();

    private DialogBox selectLabelDialog = new DialogBox(false, true); // modal
    private ListBox labelList = new ListBox();
    private TextBox newLabelName = new TextBox();
    private Anchor createLabelLink, cancelCreateLink;
    private StackPanel stack = new StackPanel();
    private Button submitButton = new Button(), cancelButton = new Button("Cancel");

    private JSONObject currentTestCondition;


    private TestLabelManager() {
        createLabelLink = new Anchor("Create new label");
        cancelCreateLink = new Anchor("Cancel create label");
        ClickHandler linkListener = new ClickHandler() {
            public void onClick(ClickEvent event) {
                if (event.getSource() == createLabelLink) {
                    stack.showStack(STACK_CREATE);
                } else {
                    stack.showStack(STACK_SELECT);
                }
            }
        };
        createLabelLink.addClickHandler(linkListener);
        cancelCreateLink.addClickHandler(linkListener);

        Panel selectPanel = new VerticalPanel();
        selectPanel.add(new HTML("Select label:"));
        selectPanel.add(labelList);
        selectPanel.add(createLabelLink);
        stack.add(selectPanel);

        Panel createPanel = new VerticalPanel();
        createPanel.add(new HTML("Enter label name:"));
        createPanel.add(newLabelName);
        createPanel.add(cancelCreateLink);
        stack.add(createPanel);

        Panel buttonPanel = new HorizontalPanel();
        buttonPanel.add(submitButton);
        buttonPanel.add(cancelButton);

        Panel dialogPanel = new VerticalPanel();
        dialogPanel.add(stack);
        dialogPanel.add(buttonPanel);
        selectLabelDialog.add(dialogPanel);

        submitButton.addClickHandler(this);
        cancelButton.addClickHandler(this);
    }

    public static TestLabelManager getManager() {
        return theInstance;
    }

    private void setLinksVisible(boolean visible) {
        createLabelLink.setVisible(visible);
        cancelCreateLink.setVisible(visible);
    }

    public void handleAddLabels(JSONObject testCondition) {
        currentTestCondition = testCondition;
        newLabelName.setText("");

        String[] labels = Utils.JSONObjectsToStrings(staticData.getData("test_labels").isArray(),
                                                     "name");
        if (labels.length == 0) {
            setLinksVisible(false);
            stack.showStack(STACK_CREATE);
        } else {
            setLinksVisible(true);
            stack.showStack(STACK_SELECT);
            populateLabelList(labels);
        }
        showDialog(ADD_TEXT);
    }

    public void handleRemoveLabels(JSONObject testCondition) {
        currentTestCondition = testCondition;

        rpcProxy.rpcCall("get_test_labels_for_tests", currentTestCondition, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                String[] labels = Utils.JSONObjectsToStrings(result.isArray(), "name");
                if (labels.length == 0) {
                    notifyManager.showMessage("No labels on selected tests");
                    return;
                }
                populateLabelList(labels);
                setLinksVisible(false);
                stack.showStack(STACK_SELECT);
                showDialog(REMOVE_TEXT);
            }
        });
    }

    private void showDialog(String actionText) {
        submitButton.setText(actionText);
        selectLabelDialog.setText(actionText);
        selectLabelDialog.center();
    }

    private void populateLabelList(String[] labels) {
        labelList.clear();
        for (String label : labels) {
            labelList.addItem(label);
        }
    }

    public void onClick(ClickEvent event) {
        selectLabelDialog.hide();

        if (event.getSource() == cancelButton) {
            return;
        }

        if (submitButton.getText().equals(ADD_TEXT)) {
            SimpleCallback doAdd = new SimpleCallback() {
                public void doCallback(Object source) {
                    addOrRemoveLabel((String) source, true);
                }
            };

            if (stack.getSelectedIndex() == STACK_CREATE) {
                addLabel(newLabelName.getText(), doAdd);
            } else {
                doAdd.doCallback(getSelectedLabel());
            }
        } else {
            assert (submitButton.getText().equals(REMOVE_TEXT));
            addOrRemoveLabel(getSelectedLabel(), false);
        }
    }

    private String getSelectedLabel() {
        return labelList.getItemText(labelList.getSelectedIndex());
    }

    private void addLabel(final String name, final SimpleCallback onFinished) {
        JSONObject args = new JSONObject();
        args.put("name", new JSONString(name));
        rpcProxy.rpcCall("add_test_label", args, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                onFinished.doCallback(name);
            }
        });
        updateLabels();
    }

    private void addOrRemoveLabel(String label, boolean add) {
        String rpcMethod;
        if (add) {
            rpcMethod = "test_label_add_tests";
        } else {
            rpcMethod = "test_label_remove_tests";
        }

        JSONObject args = Utils.copyJSONObject(currentTestCondition);
        args.put("label_id", new JSONString(label));
        rpcProxy.rpcCall(rpcMethod, args, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                notifyManager.showMessage("Labels modified successfully");
            }
        });
    }

    private void updateLabels() {
        rpcProxy.rpcCall("get_test_labels", null, new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                staticData.setData("test_labels", result);
            }
        });
    }

    public void handleInvalidate(JSONObject condition) {
        currentTestCondition = condition;
        addOrRemoveLabel(INVALIDATED_LABEL, true);
    }

    public void handleRevalidate(JSONObject condition) {
        currentTestCondition = condition;
        addOrRemoveLabel(INVALIDATED_LABEL, false);
    }
}
